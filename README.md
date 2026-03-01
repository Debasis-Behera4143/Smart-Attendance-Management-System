# 🎓 Smart Attendance Management System

## 📌 Overview

A production-ready face recognition-based attendance management system that tracks student entry and exit times, calculates duration, and automatically marks attendance status based on minimum required time.

**🎥 CCTV-Ready**: Now supports IP cameras, RTSP streams, and existing CCTV infrastructure for enterprise deployment!

## 📚 **Documentation**

### **Quick Start**:
👉 **[File Index](docs/FILE_INDEX.md)** - Quick reference for all files, one-line descriptions

### **For Developers & Technical Review**:
👉 **[Complete Technical Documentation](docs/TECHNICAL_DOCUMENTATION.md)** (1,251 lines)
- File-by-file breakdown (17 Python modules)
- All 15 libraries explained with usage examples
- System architecture & data flow diagrams
- Recognition pipeline (Hybrid HOG+CNN approach)
- Common problems & solutions implemented
- Performance metrics & benchmarks

### **For Supervisor Presentation**:
👉 **[Supervisor Presentation Guide](docs/SUPERVISOR_PRESENTATION_GUIDE.md)** (738 lines)
- How to explain the project (30-second to 20-minute versions)
- Demo scripts for each feature
- Talking points and expected questions
- Key accomplishments & innovation highlights
- Technology stack summary in simple terms

### **For Deployment**:
👉 **[Docker Deployment Guide](docs/RENDER_DOCKER_DEPLOYMENT.md)**
- Production deployment instructions
- Docker containerization
- Render.com cloud hosting

### ✨ Key Features

- 👤 **Face Data Collection**: Multi-image capture with variations
- 🔐 **Face Encoding**: High-accuracy facial recognition using deep learning
- 📹 **Entry Camera System**: Automatic entry time logging
- 📹 **Exit Camera System**: Automatic exit time and attendance marking
- 🎥 **CCTV Integration**: Support for USB, RTSP, RTMP, HTTP, and IP cameras
- ⏱️ **Duration Calculation**: Precise time tracking
- ✅ **Smart Attendance**: Auto PRESENT/ABSENT based on duration
- 📊 **Report Generation**: CSV and detailed text reports
- 🗄️ **Database Management**: SQLite-based robust storage
- 🔄 **Auto-Reconnect**: Network stream reconnection for stable CCTV operation

---

## 📁 Project Structure

```
Smart-Attendance-System/
│
├── data/                       # All data files organized here
│   ├── dataset/               # Student face images
│   │   ├── .gitkeep
│   │   ├── student_001_Name/
│   │   └── student_002_Name/
│   ├── encodings/             # Encoded face data
│   │   ├── .gitkeep
│   │   └── face_encodings.pkl
│   ├── database/              # SQLite database
│   │   ├── .gitkeep
│   │   └── attendance.db
│   ├── logs/                  # System logs
│   │   ├── .gitkeep
│   │   └── system_logs.txt
│   └── reports/               # Generated reports
│       ├── .gitkeep
│       ├── attendance_report_*.csv
│       └── daily_report_*.txt
│
├── models/                     # YOLO & ML models
│   └── yolov8n-face.pt        # YOLOv8 nano face detector
│
├── src/                        # Core source code
│   ├── attendance_manager.py  # Attendance logic & duration calc
│   ├── collect_face_data.py   # Face data collection system
│   ├── config.py              # Configuration & paths
│   ├── database_manager.py    # SQLite database operations
│   ├── encode_faces.py        # Face encoding generation
│   ├── entry_camera.py        # Entry gate system
│   ├── exit_camera.py         # Exit gate system
│   ├── rate_limiter.py        # API rate limiting
│   ├── recognition_service.py # Face recognition with YOLO
│   ├── utils.py               # Report generation utilities
│   └── validators.py          # Input validation
│
├── web/                        # Flask web application
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css      # Modern UI styling
│   │   ├── images/
│   │   │   ├── IGIT.png
│   │   │   └── MYCOMP.png
│   │   └── js/
│   │       ├── main.js        # Common utilities
│   │       ├── entry.js       # Entry gate logic
│   │       ├── exit.js        # Exit gate logic
│   │       ├── register.js    # Student registration
│   │       ├── reports.js     # Report generation
│   │       └── student_attendance.js
│   ├── templates/
│   │   ├── base.html          # Base template
│   │   ├── dashboard.html     # Main dashboard
│   │   ├── entry.html         # Entry gate UI
│   │   ├── exit.html          # Exit gate UI
│   │   ├── register.html      # Student registration UI
│   │   ├── reports.html       # Reports UI
│   │   └── student_attendance.html
│   ├── app.py                 # Flask application
│   └── wsgi.py                # Production WSGI server
│
├── .env                        # Environment configuration
├── .env.example               # Example environment file
├── .gitignore                 # Git ignore rules
├── main.py                    # CLI controller (terminal interface)
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

---

## 🔄 Complete Workflow

### **Phase 1: Face Data Collection**

```bash
python main.py
# Select Option 1: Collect Face Data
```

**What happens:**
- Camera activates
- Student enters name and roll number
- System captures 20 face images with variations
- Images saved in `dataset/student_XXX_Name/`
- Student registered in database

**Naming Convention:**
```
student_001_Debasis/
student_002_Subham/
student_003_Surya/
student_003_Suman/
```

---

### **Phase 2: Face Encoding**

```bash
python main.py
# Select Option 2: Generate Face Encodings
```

**What happens:**
- Reads all images from dataset
- Detects faces in each image
- Generates 128-dimensional face encodings
- Saves encodings to `encodings/face_encodings.pkl`

---

### **Phase 3: Entry Camera System**

```bash
python main.py
# Select Option 3: Run Entry Camera System
```

**What happens:**
- Camera monitors entry point
- Detects and recognizes faces
- Marks entry time in database
- Sets status to "INSIDE"

**Database Entry:**
```
student_id: student_001_Debasis
name: Debasis
entry_time: 2025-12-23 09:00:00
date: 2025-12-23
status: INSIDE
```

---

### **Phase 4: Exit Camera System**

```bash
python main.py
# Select Option 4: Run Exit Camera System
```

**What happens:**
- Camera monitors exit point
- Recognizes student
- Fetches entry time
- Marks exit time
- **Calculates duration**
- **Determines PRESENT/ABSENT**
- Saves final attendance

**Attendance Logic:**
```python
Duration = Exit Time - Entry Time

IF Duration >= 90 minutes:
    Status = PRESENT
ELSE:
    Status = ABSENT
```

---

## 🌐 Web Interface

The system includes a modern **Flask-based web application** with real-time camera integration and YOLO face detection.

### **Starting the Web Server**

```bash
# Development mode (recommended)
python web/wsgi.py
```

The web application will be available at: **http://127.0.0.1:5000**

### **Web Features**

- 📊 **Dashboard**: System overview and statistics
- 👨‍🎓 **Student Registration**: Capture face data through browser
- 🚪 **Entry Gate**: Real-time entry marking with webcam
- 🚶 **Exit Gate**: Real-time exit marking with attendance calculation
- 📄 **Reports**: Generate and download attendance reports
- 📊 **Student Attendance**: View individual attendance records
- 🚀 **YOLO Integration**: Optional fast face detection (toggle in Entry/Exit gates)

### **Web Application Structure**

- **Frontend**: Modern responsive UI with CSS animations
- **Backend**: Flask REST API with rate limiting
- **Camera**: WebRTC-based real-time video streaming
- **Face Recognition**: face_recognition + optional YOLO detector
- **Security**: API key authentication, rate limiting, input validation

---

## 🚀 Installation & Setup

### **1. Prerequisites**

- Python 3.8 or higher
- Webcam/Camera
- Windows/Linux/macOS

### **2. Clone/Download Project**

```bash
cd Smart-Attendance-System
```

### **3. Install Dependencies**

```bash
pip install -r requirements.txt
```

**Note:** Installing `dlib` may require:
- **Windows**: Visual Studio Build Tools
- **Linux**: `sudo apt-get install cmake`
- **macOS**: `brew install cmake`

### **4. Run the System**

```bash
python main.py
```

---

## 📋 System Menu

```
SMART ATTENDANCE MANAGEMENT SYSTEM

MAIN MENU:
  1. Collect Face Data (Register Student)
  2. Generate Face Encodings
  3. Run Entry Camera System
  4. Run Exit Camera System
  5. Generate Today's Report
  6. Generate All Attendance Report
  7. Generate Student Report
  8. View Attendance Summary
  9. Exit
```

---

## ⚙️ Configuration

Edit [`src/config.py`](src/config.py) to customize:

```python
# Attendance settings
MINIMUM_DURATION = 90  # minutes (1.5 hours)

# Camera settings
CAMERA_ENTRY_ID = 0    # Entry camera index
CAMERA_EXIT_ID = 0     # Exit camera index

# Face recognition
FACE_RECOGNITION_TOLERANCE = 0.6  # Lower = stricter
IMAGES_PER_STUDENT = 20           # Face samples
```

---

## 📊 Report Generation

### **Daily Report**
```bash
# Option 5: Generate Today's Report
```
- Summary statistics
- Detailed records
- Attendance percentage

### **Student Report**
```bash
# Option 7: Generate Student Report
```
- Individual attendance history
- Total present/absent days
- Attendance percentage

### **CSV Export**
```bash
# Option 6: Generate All Attendance Report
```
- Excel-compatible format
- All attendance records

---

## 🗄️ Database Schema

### **Students Table**
```sql
student_id | name | roll_number | registered_date
```

### **Entry Log Table**
```sql
id | student_id | name | entry_time | date | status
```

### **Exit Log Table**
```sql
id | student_id | name | entry_id | exit_time | date
```

### **Attendance Table**
```sql
id | student_id | name | entry_time | exit_time | duration | status | date
```

---

## 🎯 How to Explain

### **1. Data Collection Process**

> "We collect multiple face samples per student under controlled conditions with slight variations in pose and expression. These images are stored in a structured dataset with unique identifiers."

### **2. Face Recognition Technology**

> "We use the face_recognition library which implements deep learning-based face detection and encoding. Each face is converted into a 128-dimensional vector for comparison."

### **3. Attendance Logic**

> "The system marks entry when a student enters and exit when leaving. It calculates the duration and compares it with the minimum required time (90 minutes). Based on this, it automatically marks PRESENT or ABSENT."

### **4. Database Design**

> "We use SQLite for efficient local storage with four main tables: Students, Entry Log, Exit Log, and Attendance. This ensures data integrity and supports complex queries."

### **5. Report Generation**

> "The system generates multiple report formats including daily summaries, student-specific reports, and CSV exports for analysis."

---

## 🛠️ Troubleshooting

### **Camera not detected**
```python
# Change camera ID in config.py
CAMERA_ENTRY_ID = 1  # Try different indices
```

### **Face not recognized**
```python
# Adjust tolerance
FACE_RECOGNITION_TOLERANCE = 0.7  # Increase for easier matching
```

### **dlib installation fails**
```bash
# Windows: Install Visual C++ Build Tools
# Linux: sudo apt-get install build-essential cmake
# macOS: brew install cmake
```

---

## 🏆 Project Highlights

✅ **Industry-Standard Structure**
✅ **Modular & Scalable Code**
✅ **Complete Documentation**
✅ **Database Integration**
✅ **Real-time Processing**
✅ **Multiple Report Formats**
✅ **Error Handling**
✅ **Professional Workflow**

---

## � Deployment Options

### **Option 1: Streamlit Cloud (Recommended - FREE & Easy)**

Perfect for quick deployment with built-in camera support!

```bash
# Deploy to Streamlit Cloud
1. Go to share.streamlit.io
2. Connect your GitHub repository
3. Set main file: streamlit_app.py
4. Click Deploy!
```

📖 **Full Guide**: See [STREAMLIT_DEPLOYMENT.md](STREAMLIT_DEPLOYMENT.md)

**Files needed**: `streamlit_app.py`, `requirements-streamlit.txt`, `packages.txt`

---

### **Option 2: Local Server (Flask)**

For local network deployment (institutions/offices):

```bash
# Install dependencies
pip install -r requirements.txt

# Run Flask app (development)
python web/app.py

# Run Flask app (production with Waitress)
python web/wsgi.py
```

**Access**: `http://localhost:8080` or `http://YOUR_IP:8080`

---

### **Option 3: Cloud Platforms (Flask)**

Deploy Flask app on Render, Railway, or similar platforms:

**Files needed**: `Procfile`, `runtime.txt`, `requirements.txt`

📖 **Full Guide**: See [DEPLOYMENT.md](DEPLOYMENT.md) (if exists)

---

## �👥 Contributors

- **Debasis Behera** - Lead Developer

---

## 📄 License

MIT License - Free to use, modify, and distribute.

---

## 🙏 Acknowledgments

- Face Recognition Library: [face_recognition](https://github.com/ageitgey/face_recognition)
- OpenCV: [opencv-python](https://opencv.org/)
- SQLite: Built-in Python database

---

## 📞 Support

For any queries or issues, please refer to the documentation or raise an issue.

---

## Production Hardening (New)

### Run in production mode (Windows-friendly)

```bash
pip install -r requirements.txt
python web/wsgi.py
```

### Optional environment config

Copy `.env.example` values into your deployment environment variables and set:

- `SMART_ATTENDANCE_DEBUG=false`
- `SMART_ATTENDANCE_SECRET_KEY=<strong-random-value>`
- `SMART_ATTENDANCE_API_KEY=<strong-random-value>` (optional)
- `SMART_ATTENDANCE_REQUIRE_API_KEY=true` (if you enforce API keys)

### New API features

- `GET /api/inside-students?limit=20`
- `GET /api/analytics?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD`
- `POST /api/manual-attendance` (manual correction/upsert)

### Reliability upgrades now included

- Atomic exit + attendance writes in one DB transaction
- Request-size and image-size safeguards
- Input validation for IDs, names, dates, status values
- Rate limiting for API endpoints
- Rotating file logs with request IDs
- Pagination and filtering on `GET /api/get-attendance`
