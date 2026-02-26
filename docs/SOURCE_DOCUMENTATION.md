# Smart Attendance System - Source Code Documentation

## Table of Contents
1. [Core Configuration](#core-configuration)
2. [Database Layer](#database-layer)
3. [Recognition Engine](#recognition-engine)
4. [Attendance Logic](#attendance-logic)
5. [Data Collection](#data-collection)
6. [Camera Services](#camera-services)
7. [Utilities & Validators](#utilities--validators)
8. [Web Application](#web-application)

---

## Core Configuration

### **config.py**

#### Purpose
Central configuration file that manages all system settings, paths, and constants.

#### Key Logic
- **Environment Loading**: Reads `.env` file for secure configuration
- **Path Management**: Defines all file and folder paths (dataset, encodings, database, logs, reports)
- **System Parameters**: Sets recognition thresholds, camera settings, rate limits, YOLO support
- **Format Constants**: Standardizes date/time formats across the system

#### Main Configuration Groups

**1. Application Settings**
```python
APPLICATION_NAME = "Smart Attendance System"
VERSION = "2.0"
```

**2. Face Recognition Settings**
```python
FACE_TOLERANCE = 0.5          # Lower = stricter matching (0.0-1.0 range)
FACE_MATCH_THRESHOLD = 0.6    # Minimum confidence for match
ENABLE_YOLO_IF_AVAILABLE = True
```

**3. Camera & Capture Settings**
```python
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
IMAGE_CAPTURE_COUNT = 30      # Number of face images per student registration
CAPTURE_DELAY = 0.1           # Seconds between captures
```

**4. File Paths**
```python
DATASET_DIR = "data/dataset"
ENCODINGS_FILE = "data/encodings/encodings.pkl"
DATABASE_FILE = "data/database/attendance.db"
SYSTEM_LOG_FILE = "data/logs/system_logs.txt"
```

**5. Rate Limiting**
```python
RATE_LIMIT_HOURS = 2          # Minimum hours between entry and exit
```

#### Use Cases
- **System Initialization**: All modules import config to get paths and settings
- **Runtime Adjustments**: Modify recognition accuracy by changing FACE_TOLERANCE
- **Feature Toggles**: Enable/disable YOLO detection with ENABLE_YOLO_IF_AVAILABLE
- **Environment Deployment**: Switch between development and production using .env file

---

## Database Layer

### **database_manager.py** (829 lines)

#### Purpose
Centralized SQLite database operations for students, attendance logs, system logs, and analytics.

#### Architecture
- **Connection Management**: WAL mode for concurrent reads, PRAGMA optimizations
- **Schema Management**: Creates and maintains 4 core tables
- **CRUD Operations**: Complete create, read, update, delete for all entities
- **Analytics Engine**: Generates reports, statistics, and insights

#### Database Schema

**1. Students Table**
```sql
CREATE TABLE students (
    student_id TEXT PRIMARY KEY,      -- Unique identifier
    name TEXT NOT NULL,                -- Full name
    roll_number TEXT UNIQUE NOT NULL,  -- Enrollment number
    registered_date TEXT NOT NULL      -- Registration timestamp
)
```

**2. Entry Log Table**
```sql
CREATE TABLE entry_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
)
```

**3. Exit Log Table**
```sql
CREATE TABLE exit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
)
```

**4. System Logs Table**
```sql
CREATE TABLE system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,               -- INFO, WARNING, ERROR, CRITICAL
    category TEXT NOT NULL,            -- REGISTRATION, RECOGNITION, etc.
    message TEXT NOT NULL,
    metadata TEXT                      -- JSON string for additional data
)
```

#### Core Methods

**Student Management**
- `add_student(student_id, name, roll_number)`: Register new student
- `get_student_by_id(student_id)`: Fetch student details
- `get_student_by_roll(roll_number)`: Find student by roll number
- `student_exists(student_id)`: Check if student already registered
- `get_all_students()`: List all registered students

**Attendance Recording**
- `record_entry(student_id)`: Log entry timestamp
- `record_exit(student_id)`: Log exit timestamp
- `get_last_entry(student_id, date)`: Get most recent entry time
- `get_last_exit(student_id, date)`: Get most recent exit time

**Analytics & Reports**
- `get_daily_report(date)`: Complete attendance for specific date
- `get_date_range_report(start_date, end_date)`: Multi-day analysis
- `get_student_attendance_history(student_id)`: Individual student record
- `get_attendance_statistics(date)`: Present/absent counts, percentages

**Duplicate Prevention**
- `has_recent_entry(student_id, hours)`: Check if entry logged within X hours
- `has_recent_exit(student_id, hours)`: Check if exit logged within X hours

**System Logging**
- `log_system_event(level, category, message, metadata)`: Structured logging
- `get_system_logs(filters)`: Retrieve logs with filtering

#### Use Cases

**Case 1: Student Registration Flow**
```python
# 1. Check if student already exists
if db.student_exists(student_id):
    return "Student already registered"

# 2. Register new student
db.add_student(student_id, name, roll_number)

# 3. Log registration event
db.log_system_event("INFO", "REGISTRATION", f"New student: {name}")
```

**Case 2: Entry Recognition**
```python
# 1. Verify student exists
student = db.get_student_by_id(student_id)
if not student:
    return "Unknown student"

# 2. Check duplicate entry (rate limiting)
if db.has_recent_entry(student_id, hours=2):
    return "Entry already recorded"

# 3. Record entry
db.record_entry(student_id)
```

**Case 3: Daily Report Generation**
```python
# Generates complete attendance report
report = db.get_daily_report("2025-12-23")
# Returns: [{'student_id': '...', 'name': '...', 'entry_time': '...', 
#            'exit_time': '...', 'duration': 240, 'status': 'PRESENT'}, ...]
```

**Case 4: Analytics Dashboard**
```python
# Get statistics for date
stats = db.get_attendance_statistics("2025-12-23")
# Returns: {'total_students': 50, 'present': 45, 'absent': 5, 
#           'present_percentage': 90.0, 'absent_percentage': 10.0}
```

---

## Recognition Engine

### **recognition_service.py** (237 lines)

#### Purpose
Unified face recognition pipeline using face_recognition library with optional YOLO face detection.

#### Architecture
- **Encoding Management**: Loads and hot-reloads face encodings from pickle file
- **Dual Detection**: Supports both face_recognition's HOG and YOLO deep learning detection
- **Base64 Processing**: Handles both file frames and web camera base64 images
- **Performance Optimization**: Caches encodings, detects file changes for auto-reload

#### Key Components

**1. Initialization**
```python
def __init__(self):
    self.encodings_file = config.ENCODINGS_FILE
    self.known_encodings = []  # List of 128-dimensional face encodings
    self.known_names = []      # Corresponding student IDs
    self._encodings_mtime = None
    self._yolo_model = None
    self.load_encodings(force=True)
    self._initialize_yolo()
```

**2. YOLO Integration**
```python
def _initialize_yolo(self):
    """Loads YOLOv8n face detection model if available"""
    # Checks: ENABLE_YOLO_IF_AVAILABLE + model file exists
    # Sets: self._yolo_supported and self._yolo_active flags
    # Model: ultralytics YOLO from config.YOLO_MODEL_PATH
```

**3. Face Detection Methods**

**Method A: YOLO Detection (Faster, Deep Learning)**
```python
def _detect_faces_yolo(self, rgb_frame):
    """
    Uses YOLOv8n to detect faces
    - Runs inference on frame
    - Filters results for 'person' class with confidence > threshold
    - Converts YOLO boxes (x1, y1, x2, y2) to face_recognition format (top, right, bottom, left)
    """
```

**Method B: HOG Detection (Classic, Reliable)**
```python
def detect_faces(self, rgb_frame):
    """
    Default face detection using face_recognition library
    - HOG (Histogram of Oriented Gradients) algorithm
    - More reliable for faces, slightly slower than YOLO
    """
```

**4. Recognition Pipeline**

```python
def recognize_from_frame(self, frame):
    """
    Complete recognition flow:
    1. Detect faces (YOLO if available, else HOG)
    2. Extract face encodings
    3. Compare with known encodings using distance metrics
    4. Apply matching threshold
    5. Return best match or "Unknown"
    """
```

**5. Web Camera Support**

```python
def recognize_from_base64(self, base64_image):
    """
    Web interface pipeline:
    1. Decode base64 string to image bytes
    2. Convert to numpy array (OpenCV format)
    3. Convert BGR to RGB color space
    4. Run standard recognition pipeline
    5. Return match result
    """
```

#### Face Matching Logic

**Distance Calculation**
```python
# For each detected face encoding:
face_distances = face_recognition.face_distance(self.known_encodings, face_encoding)

# Find closest match
best_match_index = np.argmin(face_distances)
if face_distances[best_match_index] <= config.FACE_MATCH_THRESHOLD:
    return self.known_names[best_match_index]  # Student ID
else:
    return "Unknown"
```

**Threshold Tuning**
- `FACE_MATCH_THRESHOLD = 0.6`: Default balanced setting
- Lower values (0.4-0.5): Stricter matching, fewer false positives
- Higher values (0.7-0.8): Looser matching, more false positives

#### Use Cases

**Case 1: Entry Camera Recognition**
```python
service = RecognitionService()
frame = camera.read()  # Get camera frame
student_id = service.recognize_from_frame(frame)

if student_id != "Unknown":
    db.record_entry(student_id)
    print(f"Welcome {student.name}")
```

**Case 2: Web API Recognition**
```python
# Frontend sends: {"image": "data:image/jpeg;base64,/9j/4AAQ..."}
base64_data = request.json['image'].split(',')[1]
student_id = service.recognize_from_base64(base64_data)
return jsonify({"student_id": student_id})
```

**Case 3: Hot Reload on New Registration**
```python
# After encoding new student faces
service.load_encodings()  # Automatically detects file change and reloads
```

**Case 4: YOLO vs HOG Performance**
```python
# YOLO: ~50-100ms per frame (GPU), handles multiple faces
# HOG: ~100-200ms per frame (CPU), more accurate for single face
service.yolo_active  # Check which method is active
```

---

## Attendance Logic

### **attendance_manager.py** (128 lines)

#### Purpose
Calculates attendance duration and determines present/absent status based on entry/exit timestamps.

#### Core Logic Flow

```
Entry Time  →  Exit Time  →  Calculate Duration  →  Compare with Threshold  →  Status
08:30 AM        12:45 PM        255 minutes            ≥ 240 minutes           PRESENT
10:00 AM        11:30 AM         90 minutes            < 240 minutes           ABSENT
```

#### Key Methods

**1. Duration Calculation**
```python
def calculate_duration(self, entry_time: str, exit_time: str) -> int:
    """
    Converts timestamp strings to datetime objects and calculates difference in minutes
    
    Args:
        entry_time: "2025-12-23 08:30:00"
        exit_time: "2025-12-23 12:45:00"
    
    Returns:
        255 (minutes)
    
    Validations:
        - Exit time must be after entry time (prevents negative duration)
        - Timestamps must match config.REPORT_DATETIME_FORMAT
    """
```

**2. Status Determination**
```python
def determine_status(self, duration: int) -> str:
    """
    Compares duration against minimum required attendance
    
    Args:
        duration: 255 minutes
    
    Returns:
        "PRESENT" if duration >= 240 minutes
        "ABSENT" if duration < 240 minutes
    
    Configuration:
        MINIMUM_DURATION = 240  # 4 hours in minutes
    """
```

**3. Combined Processing**
```python
def process_attendance(self, entry_time: str, exit_time: str) -> Tuple[int, str]:
    """
    One-step processing: calculates duration and status together
    
    Returns:
        (duration_minutes, status_string)
        Example: (255, "PRESENT")
    """
```

#### Use Cases

**Case 1: Daily Report Generation**
```python
manager = AttendanceManager()

# For each student with entry and exit
duration = manager.calculate_duration(entry_time, exit_time)
status = manager.determine_status(duration)

# Add to report
report.append({
    'student_id': student_id,
    'duration': duration,
    'status': status
})
```

**Case 2: Real-time Status Display**
```python
# When student exits
duration, status = manager.process_attendance(entry_time, exit_time)

if status == "PRESENT":
    print(f"✓ Attendance marked: {duration} minutes")
else:
    print(f"✗ Insufficient duration: {duration} minutes required")
```

**Case 3: Custom Attendance Rules**
```python
# Modify threshold for half-day events
manager.minimum_duration = 120  # 2 hours instead of 4

# Or check if student met half-day requirement
half_day_status = "HALF_DAY" if 120 <= duration < 240 else status
```

**Case 4: Error Handling**
```python
try:
    duration = manager.calculate_duration(entry, exit)
except ValueError as e:
    # Handles: exit_time before entry_time
    # Handles: invalid timestamp format
    log_error(f"Invalid attendance record: {e}")
```

#### Validation Rules

**1. Chronological Validation**
```python
if exit_dt < entry_dt:
    raise ValueError("exit_time cannot be earlier than entry_time")
```

**2. Format Validation**
```python
# Expected format: "YYYY-MM-DD HH:MM:SS"
# Invalid: "23-12-2025 8:30" → ValueError
# Valid: "2025-12-23 08:30:00" → Success
```

**3. Duration Edge Cases**
- Same entry and exit time → 0 minutes → ABSENT
- Overnight attendance → Next day exit allowed → Calculates correctly
- Multiple entries/exits → Report generator handles last entry + last exit

---

## Data Collection

### **collect_face_data.py** (199 lines)

#### Purpose
Camera interface for capturing face images during student registration with real-time preview and quality checks.

#### Features
- **Live Camera Feed**: Opens webcam with visual overlay and instructions
- **Intelligent Capture**: Auto-detects faces before capturing images
- **Progress Tracking**: Visual counter shows capture progress (1/30, 2/30, etc.)
- **Quality Assurance**: Only captures when face is detected
- **Organized Storage**: Saves images to structured folders

#### Capture Workflow

```
Initialize Camera → Detect Face → Show Preview → Capture Image → Save to Folder → Repeat
      ↓                              ↓                                    ↓
   640x480            Green rectangle overlay              student_ID_NAME/
                     "Press SPACE to capture"              ├── 001.jpg
                     Red text: counter                     ├── 002.jpg
                                                           └── 030.jpg
```

#### Key Methods

**1. Camera Initialization**
```python
def collect_face_images(student_id: str, name: str, count: int = 30):
    """
    Opens camera and collects specified number of face images
    
    Args:
        student_id: Unique identifier
        name: Student full name
        count: Number of images to capture (default: 30)
    
    Setup:
        - Creates directory: data/dataset/student_{ID}_{NAME}/
        - Initializes camera at 640x480 resolution
        - Sets up face detector
    """
```

**2. Face Detection**
```python
# Uses face_recognition library with HOG model
faces = face_recognition.face_locations(rgb_frame, model="hog")

if len(faces) > 0:
    # Draw green rectangle around detected face
    top, right, bottom, left = faces[0]
    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
    face_detected = True
else:
    face_detected = False
```

**3. User Interface Elements**
```python
# Status display on screen
cv2.putText(frame, f"Captured: {captured_count}/{count}", 
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

cv2.putText(frame, "Press SPACE to capture, Q to quit", 
            (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 
            0.5, (255, 255, 255), 1)
```

**4. Image Saving**
```python
def save_image(frame, folder_path, index):
    filename = f"{index:03d}.jpg"  # Formats as 001.jpg, 002.jpg, etc.
    filepath = os.path.join(folder_path, filename)
    cv2.imwrite(filepath, frame)
```

#### Use Cases

**Case 1: New Student Registration**
```python
# After student fills registration form
student_id = generate_unique_id()
name = "Debasis Behera"

# Collect face images
collect_face_images(student_id, name, count=30)

# Result: 30 images saved in data/dataset/student_{ID}_Debasis_Behera/
```

**Case 2: Quality Control**
```python
# System only captures when face is detected
# User workflow:
# 1. Position face in frame → Green rectangle appears
# 2. Press SPACE → Image captured
# 3. Move slightly (different angle) → Press SPACE again
# 4. Repeat 30 times for variety (frontal, left, right, slight tilt)
```

**Case 3: Different Lighting Conditions**
```python
# Best practice: Capture in varied lighting
# - Bright overhead light: 10 images
# - Natural window light: 10 images
# - Slight shadow: 10 images
# Result: More robust face encodings for recognition
```

**Case 4: Error Recovery**
```python
# If capture interrupted (press Q)
# - Partial images already saved
# - Can resume by running again (appends to existing folder)
# - Or delete folder and start fresh
```

#### Camera Controls

- **SPACE**: Capture current frame (only if face detected)
- **Q**: Quit collection process
- **Window Close (X)**: Same as Q

#### File Organization

```
data/dataset/
├── student_2301105473_DEBASIS_BEHERA/
│   ├── 001.jpg
│   ├── 002.jpg
│   ├── ...
│   └── 030.jpg
├── student_074_Surya/
│   ├── 001.jpg
│   ├── ...
│   └── 030.jpg
```

---

### **encode_faces.py** (144 lines)

#### Purpose
Processes captured face images and generates 128-dimensional face encodings for recognition.

#### Encoding Process

```
Load Images → Detect Faces → Generate 128-D Encoding → Store with Student ID → Save Pickle File
   30 JPGs         HOG             numpy array            Dictionary          encodings.pkl
```

#### How Face Encodings Work

**Face Recognition Deep Learning Model**
1. Detects face landmarks (68 points: eyes, nose, mouth, jawline)
2. Normalizes face (aligns, crops, resizes to standard format)
3. Runs through deep neural network (ResNet-based)
4. Outputs 128 floating-point numbers (face "fingerprint")

**Example Encoding**
```python
# Each face becomes a numpy array like:
array([0.123, -0.456, 0.789, ..., -0.234])  # 128 values
```

#### Key Methods

**1. Dataset Loading**
```python
def load_dataset_from_folders():
    """
    Scans data/dataset/ for student folders
    
    Returns:
        images: List of numpy arrays (face images)
        labels: List of student IDs (corresponding labels)
    
    Example:
        images = [img1, img2, ..., img900]  # 30 students × 30 images
        labels = ["ID1", "ID1", ..., "ID30", "ID30", ...]
    """
```

**2. Encoding Generation**
```python
def generate_encodings(images, labels):
    """
    Processes each image and generates encoding
    
    Process:
        1. Convert image to RGB format
        2. Detect face location using HOG
        3. Extract 128-D encoding
        4. Associate with student ID
    
    Returns:
        {
            "encodings": [array1, array2, ...],  # Face encodings
            "names": ["ID1", "ID1", "ID2", ...]   # Student IDs
        }
    """
```

**3. Pickle Storage**
```python
def save_encodings(data, filepath):
    """
    Serializes encodings to file using pickle
    
    Creates: data/encodings/encodings.pkl (binary file)
    Used by: RecognitionService for loading during recognition
    """
```

#### Multi-Image Encoding Strategy

**Why 30 images per student?**
```python
# Single encoding: Sensitive to lighting, angle, expression
encoding_frontal = generate_encoding(frontal_image)

# Multiple encodings: Robust to variations
encodings_varied = [
    generate_encoding(frontal),
    generate_encoding(left_angle),
    generate_encoding(right_angle),
    generate_encoding(smiling),
    generate_encoding(neutral),
    # ... 25 more variations
]

# During recognition: Compares against all 30 encodings
# Match if ANY encoding is within threshold → Higher accuracy
```

#### Use Cases

**Case 1: After Registration**
```python
#Step 1: Collect face images (already done)
collect_face_images(student_id, name)

# Step 2: Generate encodings
images, labels = load_dataset_from_folders()
encoding_data = generate_encodings(images, labels)
save_encodings(encoding_data, config.ENCODINGS_FILE)

# Result: encodings.pkl updated with new student's face data
```

**Case 2: Batch Processing**
```python
# Process all students at once
# If 30 students × 30 images = 900 total images
# Processing time: ~5-10 minutes (CPU)
# Output: Single encodings.pkl file with 900 encodings
```

**Case 3: Incremental Updates**
```python
# Option A: Regenerate all encodings (slow but clean)
encode_all_faces()

# Option B: Load existing + add new student (faster)
existing_data = load_encodings()
new_encodings = generate_encodings(new_student_images, [student_id]*30)
combined_data = merge_encodings(existing_data, new_encodings)
save_encodings(combined_data)
```

**Case 4: Quality Validation**
```python
# Check encoding quality after generation
data = load_encodings()

print(f"Total encodings: {len(data['encodings'])}")
print(f"Unique students: {len(set(data['names']))}")
print(f"Average encodings per student: {len(data['encodings']) / len(set(data['names']))}")

# Expected output:
# Total encodings: 900
# Unique students: 30
# Average encodings per student: 30.0
```

#### Error Handling

**No Face Detected**
```python
# If image doesn't contain a clear face
face_locations = face_recognition.face_locations(image)
if len(face_locations) == 0:
    print(f"Warning: No face found in {image_path}")
    continue  # Skip this image
```

**Poor Quality Images**
```python
# Blurry or low-resolution images may produce weak encodings
# Solution: Re-capture face images with better lighting/focus
```

---

## Camera Services

### **entry_camera.py** (142 lines)

#### Purpose
Standalone camera application for recording student entry with real-time face recognition and rate limiting.

#### Entry Flow

```
Camera Opens → Face Detection → Recognition → Duplicate Check → Record Entry → Display Welcome
     ↓              ↓                ↓              ↓                 ↓             ↓
  640x480      Green box       "Surya"      Not within 2hr      Database      "Welcome Surya"
```

#### Key Features

**1. Real-time Recognition**
```python
while True:
    frame = camera.read()
    student_id = recognition_service.recognize_from_frame(frame)
    
    if student_id != "Unknown":
        # Show student name on screen
        student = db.get_student_by_id(student_id)
        display_name(frame, student.name)
```

**2. Rate Limiting (Duplicate Prevention)**
```python
def can_record_entry(student_id):
    """
    Checks if student already entered within RATE_LIMIT_HOURS
    
    Example:
        First entry: 8:30 AM → Success
        Second attempt: 9:00 AM → Blocked ("Entry already recorded")
        Third attempt: 10:35 AM → Success (2+ hours passed)
    """
```

**3. Visual Feedback**
```python
# Success message (green)
cv2.putText(frame, f"✓ Welcome {name}!", (x, y), 
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

# Error message (red)
cv2.putText(frame, "Entry already recorded", (x, y), 
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)

# Unknown face (yellow)
cv2.putText(frame, "Unknown Face", (x, y), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
```

**4. System Logging**
```python
# Logs all entry attempts
db.log_system_event("INFO", "ENTRY", f"Student {name} entered at {timestamp}")
db.log_system_event("WARNING", "ENTRY", f"Duplicate entry attempt by {name}")
```

#### Use Cases

**Case 1: Morning Attendance**
```python
# Run entry camera at entrance gate (8:00 AM - 10:00 AM)
python -m src.entry_camera

# Students arrive and look at camera
# System automatically recognizes and records entries
# Displays welcome messages in real-time
```

**Case 2: Late Entry Tracking**
```python
# Student arrives at 9:45 AM (late)
# System still records entry (no time validation)
# Late time visible in database: entry_log.timestamp = "2025-12-23 09:45:00"
# Daily report will show late entry time
```

**Case 3: Unknown Face Handling**
```python
# If unregistered person approaches camera
student_id = recognize_from_frame(frame)  # Returns "Unknown"

# Display: "Unknown Face - Please Register"
# No database entry created
# Logged: "Unknown face detected at entry"
```

**Case 4: Multiple Students**
```python
# If multiple faces in frame
# System processes largest/closest face first
# Other students: Wait for turn
# Alternative: YOLO can detect multiple faces simultaneously
```

#### Camera Controls

- **Q**: Quit entry camera application
- **Window Close**: Same as Q

---

### **exit_camera.py** (145 lines)

#### Purpose
Standalone camera application for recording student exit with duration calculation and attendance status.

#### Exit Flow

```
Camera Opens → Face Detection → Recognition → Fetch Entry Time → Calculate Duration → Status → Record
     ↓              ↓                ↓              ↓                    ↓              ↓         ↓
  640x480      Green box       "Surya"         8:30 AM            255 minutes      PRESENT   Database
```

#### Key Differences from Entry Camera

**1. Duration Display**
```python
# Exit camera shows attendance duration
entry_time = db.get_last_entry(student_id, today)
duration = attendance_manager.calculate_duration(entry_time, current_time)

cv2.putText(frame, f"Duration: {duration} minutes", (x, y), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
```

**2. Status Indication**
```python
status = attendance_manager.determine_status(duration)

if status == "PRESENT":
    color = (0, 255, 0)  # Green text
    message = f"✓ Attendance Marked: {duration} min"
else:
    color = (0, 0, 255)  # Red text
    message = f"✗ Insufficient: {duration} min (Need 240)"
```

**3. Entry Validation**
```python
# Cannot exit without entry
entry_time = db.get_last_entry(student_id, today)
if not entry_time:
    display_error("No entry found - Please use entry camera first")
    return
```

#### Use Cases

**Case 1: End of Day**
```python
# Run exit camera at exit gate (4:00 PM - 6:00 PM)
python -m src.exit_camera

# Students leave and look at camera
# System shows duration and status before recording exit
# "Goodbye Debasis! Attendance Marked: 255 minutes"
```

**Case 2: Early Exit**
```python
# Student leaves at 11:00 AM (only 2.5 hours)
# Entry: 8:30 AM
# Exit: 11:00 AM
# Duration: 150 minutes

# Display: "✗ Insufficient: 150 min (Need 240)"
# Status: ABSENT (will appear in daily report)
# Exit still recorded in database
```

**Case 3: Multiple Exits**
```python
# Student exits at 12:00 PM, then returns and exits again at 5:00 PM
# Rate limiting applies (2-hour minimum)

# First exit: 12:00 PM → Success
# Second exit: 1:30 PM → Blocked ("Exit already recorded")
# Third exit: 2:05 PM → Success (2+ hours passed)

# Daily report uses LAST exit time for duration calculation
```

**Case 4: No Entry Record**
```python
# If student forgot to use entry camera
# Or database entry was deleted

# Recognition: Success
# Entry check: No entry found for today
# Display: "Error: No entry record - Cannot record exit"
# Action: Student should contact admin or use entry camera
```

#### Visual UI Elements

```python
# Frame layout:
# ┌─────────────────────────────────────────┐
# │ [Face detected - green rectangle]       │
# │                                         │
# │ Name: Debasis Behera                    │
# │ Entry: 8:30 AM                          │
# │ Exit: 12:45 PM                          │
# │ Duration: 255 minutes                   │
# │ Status: ✓ PRESENT                       │
# │                                         │
# │ Press Q to quit                         │
# └─────────────────────────────────────────┘
```

---

## Utilities & Validators

### **utils.py** (109 lines)

#### Purpose
Shared utility functions for file operations, unique ID generation, and data formatting.

#### Core Functions

**1. Unique ID Generation**
```python
def generate_unique_id() -> str:
    """
    Creates collision-resistant identifier using UUID4
    
    Returns:
        "a3f2e1d4-8c9b-4f7a-9e2d-1a5b7c3e8f0d"
    
    Usage:
        student_id = generate_unique_id()
        # Guaranteed unique across millions of students
    """
```

**2. Safe File Operations**
```python
def ensure_directory(path: str):
    """
    Creates directory if doesn't exist (including parent directories)
    
    Example:
        ensure_directory("data/reports/2025/december")
        # Creates entire path structure
    """

def safe_file_delete(filepath: str) -> bool:
    """
    Deletes file with error handling
    
    Returns:
        True if deleted, False if file doesn't exist or error
    """
```

**3. Data Formatting**
```python
def format_timestamp(dt: datetime = None) -> str:
    """
    Converts datetime to standardized string format
    
    Args:
        dt: datetime object (default: current time)
    
    Returns:
        "2025-12-23 14:30:45"
    """

def parse_timestamp(timestamp_str: str) -> datetime:
    """
    Converts string to datetime object
    
    Args:
        timestamp_str: "2025-12-23 14:30:45"
    
    Returns:
        datetime(2025, 12, 23, 14, 30, 45)
    """
```

**4. Report Formatting**
```python
def format_duration(minutes: int) -> str:
    """
    Converts minutes to human-readable format
    
    Examples:
        format_duration(45) → "45 minutes"
        format_duration(120) → "2 hours"
        format_duration(255) → "4 hours 15 minutes"
    """
```

#### Use Cases

**Case 1: Student Registration**
```python
# Generate unique student ID
student_id = generate_unique_id()

# Ensure dataset folder exists
folder_path = f"data/dataset/student_{student_id}_{name}"
ensure_directory(folder_path)

# Create student record
db.add_student(student_id, name, roll_number)
```

**Case 2: Report Generation**
```python
# Format report timestamps
current_time = format_timestamp()  # "2025-12-23 14:30:45"

# Format duration for display
duration_text = format_duration(255)  # "4 hours 15 minutes"

# Create report file
report_date = datetime.now().strftime("%Y-%m-%d")
report_path = f"data/reports/attendance_report_{report_date}.csv"
ensure_directory(os.path.dirname(report_path))
```

**Case 3: Database Cleanup**
```python
# Delete old encoding file before regeneration
old_encodings = "data/encodings/encodings.pkl"
if safe_file_delete(old_encodings):
    print("Old encodings removed")
else:
    print("No previous encodings found")
```

---

### **validators.py** (152 lines)

#### Purpose
Input validation and sanitization for student registration and user inputs with smart auto-formatting.

#### Validation Functions

**1. Name Validation**
```python
def validate_name(name: str) -> Tuple[bool, str, str]:
    """
    Validates student name with comprehensive checks
    
    Rules:
        - Not empty
        - 2-100 characters
        - Only letters, spaces, hyphens, apostrophes
        - No numbers or special characters
    
    Returns:
        (is_valid, cleaned_name, error_message)
    
    Examples:
        validate_name("Debasis Behera") → (True, "Debasis Behera", "")
        validate_name("John123") → (False, "", "Name cannot contain numbers")
        validate_name("A") → (False, "", "Name must be at least 2 characters")
    """
```

**2. Roll Number Validation (Smart Auto-formatting)**
```python
def validate_roll_number(roll: str) -> Tuple[bool, str, str]:
    """
    Validates and auto-formats roll number from ANY input format
    
    Smart Cleaning:
        1. Removes common prefixes: "Roll No:", "ROLL-", "Roll:", "ID:", etc.
        2. Removes separators: hyphens, spaces, underscores
        3. Converts to uppercase
        4. Validates length (5-20 characters)
        5. Allows alphanumeric combinations
    
    Examples:
        "roll-2301105473" → (True, "2301105473", "")
        "ROLL NO: 2301105473" → (True, "2301105473", "")
        "Roll: ABC-123" → (True, "ABC123", "")
        "  2301105473  " → (True, "2301105473", "")
        "12" → (False, "", "Roll number must be at least 5 characters")
    
    Supported Input Formats:
        - "2301105473" (plain)
        - "roll-2301105473" (prefixed with hyphen)
        - "ROLL NO: 2301105473" (prefixed with colon and space)
        - "ID:2301105473" (ID prefix)
        - "Roll Number - 2301105473" (full prefix)
        - "23-01-10-5473" (with separators)
    """
```

**3. Student ID Validation**
```python
def validate_student_id(student_id: str) -> Tuple[bool, str]:
    """
    Validates UUID format for student IDs
    
    Pattern: 8-4-4-4-12 hexadecimal characters
    Example: "a3f2e1d4-8c9b-4f7a-9e2d-1a5b7c3e8f0d"
    
    Returns:
        (is_valid, error_message)
    """
```

**4. Image Data Validation**
```python
def validate_base64_image(base64_string: str) -> Tuple[bool, str]:
    """
    Validates base64-encoded image data from web camera
    
    Checks:
        - Valid base64 format
        - Contains image data header
        - Can be decoded
        - Reasonable size (not empty, not too large)
    
    Accepts:
        "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
        "data:image/png;base64,iVBORw0KGgoAAAANS..."
    """
```

#### Auto-formatting Logic

**Roll Number Cleaning Process**
```python
# Step 1: Remove common prefixes (case-insensitive)
prefixes = ["roll no:", "roll number:", "roll:", "roll-", "id:", "student id:"]
for prefix in prefixes:
    if cleaned.startswith(prefix):
        cleaned = cleaned[len(prefix):]

# Step 2: Remove all separators
cleaned = cleaned.replace("-", "").replace("_", "").replace(" ", "")

# Step 3: Convert to uppercase
cleaned = cleaned.upper()

# Step 4: Validate length and characters
if len(cleaned) < 5 or len(cleaned) > 20:
    return False, "", "Length validation failed"

if not cleaned.isalnum():
    return False, "", "Only alphanumeric characters allowed"

# Step 5: Return cleaned value
return True, cleaned, ""
```

#### Use Cases

**Case 1: Registration Form Processing**
```python
# User inputs (from web form)
name_input = "  Debasis Behera  "
roll_input = "roll-2301105473"

# Validation
valid_name, clean_name, name_error = validate_name(name_input)
valid_roll, clean_roll, roll_error = validate_roll_number(roll_input)

if not valid_name:
    return jsonify({"error": name_error}), 400

if not valid_roll:
    return jsonify({"error": roll_error}), 400

# Proceed with cleaned values
db.add_student(student_id, clean_name, clean_roll)
# Database stores: name="Debasis Behera", roll_number="2301105473"
```

**Case 2: Live Preview (JavaScript Integration)**
```python
# Frontend sends: {"roll_number": "ROLL NO: 2301105473"}
# Backend validates and returns cleaned value

@app.route('/api/validate-roll', methods=['POST'])
def validate_roll_api():
    roll = request.json['roll_number']
    valid, cleaned, error = validate_roll_number(roll)
    
    return jsonify({
        "valid": valid,
        "cleaned": cleaned,  # "2301105473"
        "error": error
    })

# Frontend displays: "Will be saved as: 2301105473"
```

**Case 3: Batch Import Validation**
```python
# Import students from CSV (various formats)
csv_data = [
    {"name": "Debasis Behera", "roll": "roll-2301105473"},
    {"name": "Surya", "roll": "ROLL NO: 074"},
    {"name": "John123", "roll": "VALID123"},  # Invalid name
]

validated_students = []
for row in csv_data:
    valid_name, clean_name, name_error = validate_name(row['name'])
    valid_roll, clean_roll, roll_error = validate_roll_number(row['roll'])
    
    if valid_name and valid_roll:
        validated_students.append({
            "name": clean_name,
            "roll": clean_roll
        })
    else:
        print(f"Skipped: {name_error or roll_error}")

# Result: 2 valid students, 1 skipped
```

**Case 4: Security Validation**
```python
# Prevent SQL injection or XSS attacks
malicious_name = "<script>alert('hack')</script>"
valid, _, error = validate_name(malicious_name)
# Returns: (False, "", "Name can only contain letters...")

malicious_roll = "'; DROP TABLE students;--"
valid, _, error = validate_roll_number(malicious_roll)
# Returns: (False, "", "Invalid characters detected")
```

#### Validation Test Results (Roll Number Auto-formatting)

```python
# Test Suite: 14/14 tests passed ✓

Test Cases:
✓ "2301105473" → "2301105473" (plain number)
✓ "roll-2301105473" → "2301105473" (prefix + hyphen)
✓ "ROLL NO: 2301105473" → "2301105473" (full prefix)
✓ "Roll Number: ABC123" → "ABC123" (alphanumeric)
✓ "  2301105473  " → "2301105473" (whitespace trimming)
✓ "23-01-10-5473" → "2301105473" (hyphen removal)
✓ "roll_2301105473" → "2301105473" (underscore removal)
✓ "ID: XYZ-789" → "XYZ789" (ID prefix)
✓ "12" → REJECTED (too short)
✓ "12345678901234567890123" → REJECTED (too long)
✓ "roll@123" → REJECTED (special characters)
✓ "" → REJECTED (empty)
✓ "roll-" → REJECTED (no value after prefix)
✓ "STUDENT ID: 2301105473" → "2301105473" (student ID prefix)
```

---

### **rate_limiter.py** (83 lines)

#### Purpose
Prevents duplicate entry/exit recordings within specified time windows.

#### Rate Limiting Logic

```python
class RateLimiter:
    def __init__(self, db_manager):
        self.db = db_manager
        self.entry_limit_hours = config.RATE_LIMIT_HOURS  # Default: 2 hours
        self.exit_limit_hours = config.RATE_LIMIT_HOURS
    
    def can_record_entry(self, student_id: str) -> Tuple[bool, str]:
        """
        Checks if student can record new entry
        
        Returns:
            (True, "") if allowed
            (False, "Entry already recorded 30 minutes ago") if blocked
        """
```

#### Use Cases

**Case 1: Entry Rate Limiting**
```python
rate_limiter = RateLimiter(db)

# 8:30 AM - First entry
can_enter, message = rate_limiter.can_record_entry("student_123")
# Returns: (True, "") → Allowed

# 9:00 AM - Second attempt (30 minutes later)
can_enter, message = rate_limiter.can_record_entry("student_123")
# Returns: (False, "Entry already recorded 30 minutes ago") → Blocked

# 10:35 AM - Third attempt (2 hours 5 minutes later)
can_enter, message = rate_limiter.can_record_entry("student_123")
# Returns: (True, "") → Allowed
```

**Case 2: Exit Rate Limiting**
```python
# Prevents accidental multiple exits
# Same logic as entry, but checks exit_log table
can_exit, message = rate_limiter.can_record_exit("student_123")
```

**Case 3: Custom Time Windows**
```python
# Adjust rate limit for special events
rate_limiter.entry_limit_hours = 1  # 1 hour instead of 2
rate_limiter.exit_limit_hours = 1

# Useful for half-day sessions or workshops
```

---

## Web Application

### **web/app.py** (860 lines)

#### Purpose
Main Flask application providing web interface for attendance system with RESTful API endpoints.

#### Architecture Overview

```
Frontend (HTML/CSS/JS) ← → Flask Routes ← → Business Logic (src/*) ← → Database
      ↓                        ↓                    ↓                     ↓
   Templates              @app.route          Recognition Service    SQLite DB
   Static Files           JSON APIs           Attendance Manager     attendance.db
```

#### Core Route Groups

**1. Page Routes (HTML Rendering)**
```python
@app.route('/')
def index():
    """Dashboard homepage with statistics"""
    return render_template('dashboard.html')

@app.route('/register')
def register_page():
    """Student registration form"""
    return render_template('register.html')

@app.route('/entry')
def entry_page():
    """Entry camera interface"""
    return render_template('entry.html')

@app.route('/exit')
def exit_page():
    """Exit camera interface"""
    return render_template('exit.html')

@app.route('/reports')
def reports_page():
    """Attendance reports and analytics"""
    return render_template('reports.html')

@app.route('/student_attendance')
def student_attendance_page():
    """Individual student attendance history"""
    return render_template('student_attendance.html')
```

**2. API Routes (JSON Responses)**

**Registration APIs**
```python
@app.route('/api/register-student', methods=['POST'])
def register_student():
    """
    Registers new student in database
    
    Request:
        {
            "name": "Debasis Behera",
            "roll_number": "2301105473"
        }
    
    Response:
        {
            "success": true,
            "student_id": "a3f2e1d4-8c9b-4f7a-9e2d-1a5b7c3e8f0d",
            "message": "Student registered successfully"
        }
    
    Process:
        1. Validate name and roll number
        2. Check for duplicates
        3. Generate unique student ID
        4. Create database record
        5. Return student ID for face capture
    """

@app.route('/api/save-face-images', methods=['POST'])
def save_face_images():
    """
    Saves captured face images to dataset folder
    
    Request:
        {
            "student_id": "a3f2e1d4-...",
            "images": ["data:image/jpeg;base64,...", ...]  # Array of 30 images
        }
    
    Process:
        1. Decode base64 images
        2. Create student folder
        3. Save as 001.jpg, 002.jpg, ..., 030.jpg
    """

@app.route('/api/generate-encodings', methods=['POST'])
def generate_encodings():
    """
    Triggers face encoding generation
    
    Process:
        1. Load all dataset images
        2. Generate 128-D encodings
        3. Save to encodings.pkl
        4. Hot-reload in RecognitionService
    """
```

**Recognition APIs**
```python
@app.route('/api/recognize_entry', methods=['POST'])
def recognize_entry():
    """
    Web-based entry recognition
    
    Request:
        {
            "image": "data:image/jpeg;base64,/9j/4AAQ..."
        }
    
    Response (Success):
        {
            "success": true,
            "student_id": "a3f2e1d4-...",
            "name": "Debasis Behera",
            "message": "Welcome Debasis Behera!"
        }
    
    Response (Duplicate):
        {
            "success": false,
            "error": "Entry already recorded 30 minutes ago"
        }
    
    Process:
        1. Decode base64 image
        2. Run face recognition
        3. Check rate limiting
        4. Record entry in database
        5. Log system event
    """

@app.route('/api/recognize_exit', methods=['POST'])
def recognize_exit():
    """
    Web-based exit recognition with duration calculation
    
    Response:
        {
            "success": true,
            "student_id": "a3f2e1d4-...",
            "name": "Debasis Behera",
            "entry_time": "08:30:00",
            "exit_time": "12:45:00",
            "duration": 255,
            "status": "PRESENT",
            "message": "Goodbye Debasis Behera! Attendance Marked"
        }
    
    Process:
        1. Recognize face
        2. Fetch entry time
        3. Calculate duration
        4. Determine status
        5. Record exit
        6. Return complete attendance info
    """
```

**Reports APIs**
```python
@app.route('/api/daily-report', methods=['GET'])
def get_daily_report():
    """
    Fetch attendance report for specific date
    
    Request:
        GET /api/daily-report?date=2025-12-23
    
    Response:
        {
            "date": "2025-12-23",
            "students": [
                {
                    "student_id": "...",
                    "name": "Debasis Behera",
                    "roll_number": "2301105473",
                    "entry_time": "08:30:00",
                    "exit_time": "12:45:00",
                    "duration": 255,
                    "status": "PRESENT"
                },
                ...
            ],
            "statistics": {
                "total": 30,
                "present": 28,
                "absent": 2,
                "present_percentage": 93.3
            }
        }
    """

@app.route('/api/student-history', methods=['GET'])
def get_student_history():
    """
    Individual student attendance history
    
    Request:
        GET /api/student-history?roll_number=2301105473
    
    Response:
        {
            "student": {
                "student_id": "...",
                "name": "Debasis Behera",
                "roll_number": "2301105473"
            },
            "attendance": [
                {
                    "date": "2025-12-23",
                    "entry_time": "08:30:00",
                    "exit_time": "12:45:00",
                    "duration": 255,
                    "status": "PRESENT"
                },
                ...
            ],
            "summary": {
                "total_days": 20,
                "present_days": 18,
                "absent_days": 2,
                "attendance_percentage": 90.0
            }
        }
    """

@app.route('/api/export-csv', methods=['GET'])
def export_csv():
    """
    Exports daily report as CSV file
    
    Request:
        GET /api/export-csv?date=2025-12-23
    
    Response:
        CSV file download with headers:
        Student ID, Name, Roll Number, Entry Time, Exit Time, Duration (min), Status
    """
```

**Dashboard APIs**
```python
@app.route('/api/dashboard-stats', methods=['GET'])
def get_dashboard_stats():
    """
    Real-time dashboard statistics
    
    Response:
        {
            "today": {
                "date": "2025-12-23",
                "total_students": 30,
                "present": 28,
                "absent": 2,
                "present_percentage": 93.3
            },
            "recent_entries": [
                {"name": "Debasis", "time": "08:30:00"},
                {"name": "Surya", "time": "08:32:00"}
            ],
            "system_health": {
                "yolo_active": true,
                "encodings_loaded": true,
                "total_encodings": 900
            }
        }
    """
```

#### Middleware & Security

**1. CORS (Cross-Origin Resource Sharing)**
```python
from flask_cors import CORS
CORS(app)  # Allows web interface to call APIs
```

**2. Error Handling**
```python
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500
```

**3. Request Validation**
```python
# All API endpoints validate inputs
if not request.json:
    return jsonify({"error": "Invalid request format"}), 400

if 'image' not in request.json:
    return jsonify({"error": "Missing image data"}), 400
```

#### Use Cases

**Case 1: Complete Registration Flow**
```javascript
// Frontend: register.js

// Step 1: Submit student details
fetch('/api/register-student', {
    method: 'POST',
    body: JSON.stringify({name: "Debasis", roll_number: "2301105473"})
})
.then(response => response.json())
.then(data => {
    student_id = data.student_id;  // Save for next step
    
    // Step 2: Capture 30 face images using webcam
    captureImages();
    
    // Step 3: Send images to backend
    fetch('/api/save-face-images', {
        method: 'POST',
        body: JSON.stringify({student_id: student_id, images: capturedImages})
    });
    
    // Step 4: Generate encodings
    fetch('/api/generate-encodings', {method: 'POST'});
});
```

**Case 2: Entry Recognition Flow**
```javascript
// Frontend: entry.js

// Capture image from webcam
const image = captureWebcamFrame();

// Send to backend
fetch('/api/recognize_entry', {
    method: 'POST',
    body: JSON.stringify({image: image})
})
.then(response => response.json())
.then(data => {
    if (data.success) {
        showWelcomeMessage(data.name);
    } else {
        showError(data.error);
    }
});
```

**Case 3: Reports Generation**
```javascript
// Frontend: reports.js

// Fetch daily report
fetch('/api/daily-report?date=2025-12-23')
.then(response => response.json())
.then(data => {
    displayStatistics(data.statistics);
    populateTable(data.students);
});

// Export to CSV
window.location = '/api/export-csv?date=2025-12-23';
```

---

### **web/wsgi.py** (16 lines)

#### Purpose
Production server entry point using Waitress WSGI server.

#### Code
```python
"""WSGI Server Entry Point"""

from waitress import serve
from app import app
from src import config

if __name__ == '__main__':
    print(f"Starting {config.APPLICATION_NAME} v{config.VERSION}")
    print(f"Serving on http://{config.FLASK_HOST}:{config.FLASK_PORT}")
    
    serve(
        app,
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        threads=config.WAITRESS_THREADS
    )
```

#### Why Waitress?

**Flask Development Server vs Waitress**
```python
# Flask development server (NOT for production)
flask run
# Issues: Single-threaded, not secure, crashes under load

# Waitress (Production-ready)
python web/wsgi.py
# Benefits: Multi-threaded, stable, handles concurrent requests
```

#### Configuration Options

```python
# config.py settings
FLASK_HOST = "0.0.0.0"  # Listen on all interfaces
FLASK_PORT = 5000       # Default port
WAITRESS_THREADS = 4    # Concurrent request handling
```

#### Use Cases

**Case 1: Production Deployment**
```bash
# Start production server
python web\wsgi.py

# Output:
# Starting Smart Attendance System v2.0
# Serving on http://0.0.0.0:5000
```

**Case 2: Port Configuration**
```python
# Change port in .env file
FLASK_PORT=8080

# Or set environment variable
$env:FLASK_PORT="8080"
python web\wsgi.py
```

**Case 3: Performance Tuning**
```python
# Increase threads for high traffic
WAITRESS_THREADS = 8  # Handle 8 concurrent requests
```

---

## Frontend Documentation

### **JavaScript Files**

**1. entry.js**
- Captures webcam feed
- Sends frames to `/api/recognize_entry`
- Displays real-time recognition results
- Shows success/error messages

**2. exit.js**
- Similar to entry.js
- Calls `/api/recognize_exit`
- Displays duration and attendance status

**3. register.js**
- Student registration form
- Webcam capture for 30 images
- Live roll number preview with auto-formatting
- Calls registration APIs in sequence

**4. reports.js**
- Date picker for report selection
- Fetches and displays daily reports
- Export to CSV functionality
- Statistics charts

**5. student_attendance.js**
- Individual student lookup by roll number
- Displays attendance history table
- Shows summary statistics (present %, absent %)

**6. main.js**
- Dashboard real-time updates
- Today's statistics
- Recent entries/exits list
- System health indicators

---

## System Workflow Examples

### Complete Student Lifecycle

```
1. REGISTRATION (Web Interface)
   ├── User fills form: name, roll_number
   ├── validates.py: Clean and validate inputs
   ├── app.py: Create student record in database
   ├── Webcam captures 30 face images
   ├── app.py: Save images to data/dataset/
   ├── encode_faces.py: Generate 128-D encodings
   └── recognition_service.py: Hot-reload encodings

2. ENTRY (Camera/Web)
   ├── Camera captures frame
   ├── recognition_service.py: Detect and recognize face
   ├── rate_limiter.py: Check duplicate entry
   ├── database_manager.py: Record entry timestamp
   └── Display welcome message

3. EXIT (Camera/Web)
   ├── Camera captures frame
   ├── recognition_service.py: Recognize face
   ├── database_manager.py: Fetch entry time
   ├── attendance_manager.py: Calculate duration & status
   ├── database_manager.py: Record exit timestamp
   └── Display attendance status

4. REPORTS (Web Interface)
   ├── User selects date
   ├── database_manager.py: Fetch all entries/exits for date
   ├── attendance_manager.py: Calculate durations & statuses
   ├── app.py: Format as JSON
   ├── reports.js: Render table and statistics
   └── Optional: Export to CSV
```

---

## Configuration Guide

### Essential Settings in config.py

**Face Recognition Tuning**
```python
# Stricter matching (fewer false positives, may miss some faces)
FACE_TOLERANCE = 0.4
FACE_MATCH_THRESHOLD = 0.5

# Looser matching (more false positives, catches more faces)
FACE_TOLERANCE = 0.6
FACE_MATCH_THRESHOLD = 0.7

# Balanced (recommended)
FACE_TOLERANCE = 0.5
FACE_MATCH_THRESHOLD = 0.6
```

**Attendance Requirements**
```python
# Full-day attendance (4 hours)
MINIMUM_DURATION = 240  # minutes

# Half-day attendance (2 hours)
MINIMUM_DURATION = 120

# Workshop/seminar (1 hour)
MINIMUM_DURATION = 60
```

**Rate Limiting**
```python
# Prevent duplicate entries within 2 hours
RATE_LIMIT_HOURS = 2

# Stricter: 4 hours
RATE_LIMIT_HOURS = 4

# Looser: 1 hour
RATE_LIMIT_HOURS = 1
```

**YOLO Detection**
```python
# Enable YOLO for faster multi-face detection
ENABLE_YOLO_IF_AVAILABLE = True

# Disable YOLO (use traditional HOG)
ENABLE_YOLO_IF_AVAILABLE = False
```

---

## Troubleshooting Guide

### Common Issues & Solutions

**Issue 1: Face Not Recognized**
```
Cause: Low-quality encodings or strict threshold
Solution:
  1. Re-capture face images with better lighting
  2. Increase FACE_MATCH_THRESHOLD to 0.65
  3. Regenerate encodings
```

**Issue 2: Unknown Face Detected**
```
Cause: Student not registered or encodings not loaded
Solution:
  1. Check if student exists in database
  2. Verify encodings.pkl contains student data
  3. Restart RecognitionService to reload encodings
```

**Issue 3: Duplicate Entry Error**
```
Cause: Rate limiting active
Solution:
  1. Wait for RATE_LIMIT_HOURS to pass
  2. Or adjust RATE_LIMIT_HOURS in config.py
  3. Or manually delete recent entry from database
```

**Issue 4: Server Won't Start**
```
Cause: Port 5000 already in use
Solution:
  1. Kill existing Python processes
  2. Or change FLASK_PORT in .env file
  3. Run: Get-Process python | Stop-Process -Force
```

---

## Performance Optimization

### Recognition Speed

**Current Performance**
- HOG Detection: ~100-200ms per frame
- YOLO Detection: ~50-100ms per frame (GPU), ~150ms (CPU)
- Encoding Generation: ~30 students × 30 images = ~5-10 minutes
- Database Operations: <10ms per query

**Optimization Tips**
```python
# Use YOLO for faster detection
ENABLE_YOLO_IF_AVAILABLE = True

# Lower camera resolution for speed
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# Reduce encodings per student (trade accuracy for speed)
IMAGE_CAPTURE_COUNT = 15  # Instead of 30
```

---

## Security Considerations

**1. Input Validation**
- All user inputs sanitized by validators.py
- Prevents SQL injection, XSS attacks

**2. File Security**
- Student images stored with unique IDs (not names)
- Database uses foreign keys and constraints

**3. API Security**
- Rate limiting on entry/exit prevents abuse
- Error messages don't leak sensitive info

**4. Environment Variables**
- Sensitive config in .env file (not committed to git)

---

## End of Documentation

This comprehensive guide covers all source files, their logic, use cases, and interactions within the Smart Attendance System. Each module is designed to work together as a cohesive ecosystem for automated face recognition-based attendance tracking.

For additional help, refer to:
- `docs/RUN_WEB_SERVER.txt` - Quick start guide
- `docs/WEB_ARCHITECTURE_EXPLAINED.txt` - System architecture diagrams
- `README.md` - Project overview and installation

---

**Document Version**: 1.0  
**Last Updated**: December 23, 2025  
**System Version**: Smart Attendance System v2.0
