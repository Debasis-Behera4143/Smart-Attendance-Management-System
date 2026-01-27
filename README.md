# 🎓 Smart Attendance Management System

## 📌 Overview

A **final-year level** face recognition-based attendance management system that tracks student entry and exit times, calculates duration, and automatically marks attendance status based on minimum required time.

### ✨ Key Features

- 👤 **Face Data Collection**: Multi-image capture with variations
- 🔐 **Face Encoding**: High-accuracy facial recognition using deep learning
- 📹 **Entry Camera System**: Automatic entry time logging
- 📹 **Exit Camera System**: Automatic exit time and attendance marking
- ⏱️ **Duration Calculation**: Precise time tracking
- ✅ **Smart Attendance**: Auto PRESENT/ABSENT based on duration
- 📊 **Report Generation**: CSV and detailed text reports
- 🗄️ **Database Management**: SQLite-based robust storage

---

## 📁 Project Structure

```
Smart-Attendance-System/
│
├── dataset/                    # Student face images
│   ├── student_001_Debasis/
│   ├── student_002_Rahul/
│   └── ...
│
├── encodings/                  # Encoded face data
│   └── face_encodings.pkl
│
├── database/                   # SQLite database
│   └── attendance.db
│
├── models/                     # ML models (optional)
│   └── face_detector.xml
│
├── logs/                       # System logs
│   └── system_logs.txt
│
├── reports/                    # Generated reports
│   ├── attendance_report.csv
│   └── daily_report_*.txt
│
├── src/                        # Source code
│   ├── collect_face_data.py   # Face data collection
│   ├── encode_faces.py        # Face encoding generation
│   ├── entry_camera.py        # Entry point system
│   ├── exit_camera.py         # Exit point system
│   ├── attendance_manager.py  # Attendance logic
│   ├── database_manager.py    # Database operations
│   ├── utils.py               # Report generation
│   └── config.py              # Configuration
│
├── main.py                     # Main controller
├── requirements.txt            # Dependencies
└── README.md                   # Documentation
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
student_002_Rahul/
student_003_Priya/
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

## 🎯 How to Explain in Viva

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

## 👥 Contributors

- **Your Name** - Final Year Project

---

## 📄 License

This project is created for educational purposes as a final-year project.

---

## 🙏 Acknowledgments

- Face Recognition Library: [face_recognition](https://github.com/ageitgey/face_recognition)
- OpenCV: [opencv-python](https://opencv.org/)
- SQLite: Built-in Python database

---

## 📞 Support

For any queries or issues, please refer to the documentation or raise an issue.

---

**Made with ❤️ for Academic Excellence**
