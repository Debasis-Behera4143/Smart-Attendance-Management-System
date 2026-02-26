# 📁 File Organization Guide

## 🎯 Purpose of Each File

### **Core Application Files**

| File | Purpose | Required For |
|------|---------|--------------|
| `main.py` | CLI interface for terminal-based operations | Local development |
| `web/app.py` | Flask web application | Flask deployment |
| `web/wsgi.py` | Production WSGI server (Waitress) | Flask production |
| `streamlit_app.py` | Streamlit web application | **Streamlit deployment** ⭐ |

---

### **Deployment Files**

#### **For Streamlit Cloud (Recommended)**
- ✅ `streamlit_app.py` - Main app file
- ✅ `requirements-streamlit.txt` - Python dependencies
- ✅ `packages.txt` - System dependencies (Linux)
- ✅ `.streamlit/config.toml` - App configuration

#### **For Flask (Heroku/Render/Railway)**
- ✅ `Procfile` - Process file for deployment
- ✅ `runtime.txt` - Python version specification
- ✅ `requirements.txt` - Python dependencies
- ✅ `web/wsgi.py` - WSGI server entry point

#### **For Local Development (Flask)**
- ✅ `requirements.txt` - All dependencies
- ✅ `web/app.py` - Development server
- ✅ `.env.example` - Environment variable template

---

### **Configuration Files**

| File | Purpose |
|------|---------|
| `.env.example` | Template for environment variables |
| `.env` | Actual environment variables (git-ignored) |
| `.gitignore` | Files to exclude from Git |
| `src/config.py` | Application configuration |

---

### **Documentation Files**

| File | Purpose | Keep? |
|------|---------|-------|
| `README.md` | Main project documentation | ✅ Yes |
| `STREAMLIT_DEPLOYMENT.md` | Streamlit deployment guide | ✅ Yes |
| `docs/SOURCE_DOCUMENTATION.md` | Detailed API documentation | ✅ Yes |
| `docs/SOURCE_CODE_DETAILED_GUIDE.md` | Source code guide | ✅ Yes |

---

### **Source Code (`src/`)**

All core Python modules:
- `attendance_manager.py` - Attendance logic
- `database_manager.py` - Database operations
- `recognition_service.py` - Face recognition
- `encode_faces.py` - Face encoding
- `collect_face_data.py` - Data collection
- `entry_camera.py` - Entry system
- `exit_camera.py` - Exit system
- `rate_limiter.py` - API rate limiting
- `validators.py` - Input validation
- `utils.py` - Utilities & report generation
- `config.py` - Configuration

---

### **Data Directories** (Git-ignored, created at runtime)

```
data/
├── dataset/        # Student face images
├── encodings/      # Face encodings (.pkl)
├── database/       # SQLite database
├── logs/           # System logs
└── reports/        # Generated reports
```

---

### **Web Application (`web/`)**

```
web/
├── app.py                    # Flask application
├── wsgi.py                   # Production server
├── static/
│   ├── css/style.css        # Styling
│   ├── images/              # Logo images
│   └── js/                  # Frontend JavaScript
└── templates/               # HTML templates
    ├── base.html
    ├── dashboard.html
    ├── entry.html
    ├── exit.html
    ├── register.html
    ├── reports.html
    └── student_attendance.html
```

---

## 🗑️ Files You Can Safely Remove

**None currently!** All files serve a purpose:

- **Flask deployment files** (Procfile, runtime.txt) - Keep for Flask cloud deployment options
- **Streamlit files** - Keep for Streamlit deployment
- **Documentation** - All serve different purposes

---

## 🎯 Quick Decision Guide

### **"I want to deploy for FREE with camera support"**
→ Use **Streamlit Cloud**
→ Files needed: `streamlit_app.py`, `requirements-streamlit.txt`, `packages.txt`, `.streamlit/`

### **"I want to deploy on my college server"**
→ Use **Flask (local)**
→ Files needed: `web/`, `requirements.txt`, `src/`

### **"I want professional cloud deployment"**
→ Use **Flask + Render/Railway**
→ Files needed: `Procfile`, `runtime.txt`, `requirements.txt`, `web/`, `src/`

---

## 📝 Summary

- **Keep all files** - they support different deployment methods
- **Both Flask and Streamlit apps** work independently
- **Choose based on your needs**:
  - Streamlit = Easiest, FREE, quick demo
  - Flask = More control, production-ready

---

✅ **All files are organized and necessary!**
