"""Streamlit Web App for Smart Attendance Management System."""

import os
import sys
import streamlit as st
import cv2
import pandas as pd
from datetime import datetime, date
from PIL import Image
import io
import base64

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import src.config as config
from src.attendance_manager import AttendanceManager
from src.database_manager import DatabaseManager
from src.encode_faces import FaceEncoder
from src.recognition_service import RecognitionService
from src.utils import ReportGenerator

# Page config
st.set_page_config(
    page_title="Smart Attendance System",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        text-align: center;
        color: #1f77b4;
        padding: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 30px;
    }
    .metric-card {
        background: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
    }
    .success-box {
        padding: 10px;
        border-radius: 5px;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .error-box {
        padding: 10px;
        border-radius: 5px;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'db_manager' not in st.session_state:
    st.session_state.db_manager = DatabaseManager()
if 'recognition_service' not in st.session_state:
    st.session_state.recognition_service = RecognitionService()
if 'attendance_manager' not in st.session_state:
    st.session_state.attendance_manager = AttendanceManager()
if 'face_encoder' not in st.session_state:
    st.session_state.face_encoder = FaceEncoder()

# Header
st.markdown('<div class="main-header"><h1>🎓 Smart Attendance System</h1><p>Face Recognition Based Attendance Management</p></div>', unsafe_allow_html=True)

# Sidebar navigation
st.sidebar.title("📋 Navigation")
page = st.sidebar.radio("Go to", ["🏠 Dashboard", "✍️ Register Student", "📥 Entry", "📤 Exit", "📊 Reports", "👤 Student Attendance"])

# Dashboard Page
if page == "🏠 Dashboard":
    st.header("📊 Dashboard")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_students = st.session_state.db_manager.get_total_students()
        st.metric("Total Students", total_students, delta=None)
    
    with col2:
        today = date.today().isoformat()
        present_count = st.session_state.db_manager.get_present_count_for_date(today)
        st.metric("Present Today", present_count)
    
    with col3:
        active_entries = st.session_state.db_manager.get_active_entry_count()
        st.metric("Currently In Campus", active_entries)
    
    with col4:
        avg_duration = st.session_state.db_manager.get_average_duration_today()
        st.metric("Avg Duration (min)", f"{avg_duration:.1f}" if avg_duration else "0")
    
    # Recent attendance
    st.subheader("📋 Recent Attendance (Last 10)")
    recent = st.session_state.db_manager.get_recent_attendance(limit=10)
    if recent:
        df = pd.DataFrame(recent)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No attendance records yet")

# Register Student Page
elif page == "✍️ Register Student":
    st.header("✍️ Register New Student")
    
    with st.form("register_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            roll_number = st.text_input("Roll Number *", placeholder="e.g., 21BCE001")
            name = st.text_input("Full Name *", placeholder="e.g., John Doe")
        
        with col2:
            subject = st.text_input("Subject/Course *", placeholder="e.g., Computer Science")
            num_images = st.number_input("Number of Images", min_value=10, max_value=50, value=30)
        
        st.info("📸 After clicking Register, you'll need to capture face images via your camera")
        submit = st.form_submit_button("Register Student")
        
        if submit:
            if not roll_number or not name or not subject:
                st.error("Please fill all required fields!")
            else:
                # Check if student exists
                existing = st.session_state.db_manager.get_student_by_roll_number(roll_number)
                if existing:
                    st.error(f"Student with roll number {roll_number} already exists!")
                else:
                    # Add student to database
                    student_id = st.session_state.db_manager.add_student(roll_number, name, subject)
                    if student_id:
                        st.success(f"✅ Student registered successfully! ID: {student_id}")
                        st.info("📸 Now use the camera to capture face images. In production, integrate webcam capture here.")
                    else:
                        st.error("Failed to register student")

# Entry Page
elif page == "📥 Entry":
    st.header("📥 Entry Gate")
    
    st.info("💡 Use your webcam to capture student face for entry")
    
    # Camera input
    camera_image = st.camera_input("Take a picture for Entry")
    
    if camera_image:
        # Convert to PIL Image
        image = Image.open(camera_image)
        
        # Display image
        col1, col2 = st.columns([1, 1])
        with col1:
            st.image(image, caption="Captured Image", use_container_width=True)
        
        with col2:
            with st.spinner("🔍 Recognizing face..."):
                # Convert PIL to cv2 format
                img_array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                
                # Recognize face
                result = st.session_state.recognition_service.recognize_face(img_array)
                
                if result["success"] and result["student"]:
                    student = result["student"]
                    st.markdown(f'<div class="success-box"><h3>✅ Welcome!</h3><p><strong>Name:</strong> {student["name"]}<br><strong>Roll:</strong> {student["roll_number"]}<br><strong>Subject:</strong> {student["subject"]}</p></div>', unsafe_allow_html=True)
                    
                    # Record entry
                    entry_time = datetime.now()
                    success = st.session_state.attendance_manager.record_entry(
                        student["id"],
                        entry_time
                    )
                    
                    if success:
                        st.success(f"Entry recorded at {entry_time.strftime('%H:%M:%S')}")
                    else:
                        st.warning("Entry already recorded today")
                else:
                    st.markdown('<div class="error-box"><h3>❌ Not Recognized</h3><p>Face not found in database. Please register first.</p></div>', unsafe_allow_html=True)

# Exit Page
elif page == "📤 Exit":
    st.header("📤 Exit Gate")
    
    st.info("💡 Use your webcam to capture student face for exit")
    
    # Camera input
    camera_image = st.camera_input("Take a picture for Exit")
    
    if camera_image:
        # Convert to PIL Image
        image = Image.open(camera_image)
        
        # Display image
        col1, col2 = st.columns([1, 1])
        with col1:
            st.image(image, caption="Captured Image", use_container_width=True)
        
        with col2:
            with st.spinner("🔍 Recognizing face..."):
                # Convert PIL to cv2 format
                import numpy as np
                img_array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                
                # Recognize face
                result = st.session_state.recognition_service.recognize_face(img_array)
                
                if result["success"] and result["student"]:
                    student = result["student"]
                    st.markdown(f'<div class="success-box"><h3>👋 Goodbye!</h3><p><strong>Name:</strong> {student["name"]}<br><strong>Roll:</strong> {student["roll_number"]}<br><strong>Subject:</strong> {student["subject"]}</p></div>', unsafe_allow_html=True)
                    
                    # Record exit
                    exit_time = datetime.now()
                    result = st.session_state.attendance_manager.record_exit(
                        student["id"],
                        exit_time
                    )
                    
                    if result["success"]:
                        st.success(f"✅ Exit recorded at {exit_time.strftime('%H:%M:%S')}")
                        if result.get("duration_minutes"):
                            st.info(f"⏱️ Duration: {result['duration_minutes']} minutes")
                            st.info(f"📊 Status: {result.get('status', 'N/A')}")
                    else:
                        st.error(result.get("message", "Failed to record exit"))
                else:
                    st.markdown('<div class="error-box"><h3>❌ Not Recognized</h3><p>Face not found in database.</p></div>', unsafe_allow_html=True)

# Reports Page
elif page == "📊 Reports":
    st.header("📊 Attendance Reports")
    
    # Date filter
    col1, col2, col3 = st.columns(3)
    with col1:
        report_date = st.date_input("Select Date", value=date.today())
    with col2:
        report_type = st.selectbox("Report Type", ["Daily Report", "CSV Export"])
    with col3:
        status_filter = st.selectbox("Filter by Status", ["All", "PRESENT", "ABSENT"])
    
    if st.button("Generate Report"):
        date_str = report_date.isoformat()
        
        # Get attendance records
        records = st.session_state.db_manager.get_attendance_by_date(
            date_str,
            status=None if status_filter == "All" else status_filter
        )
        
        if records:
            df = pd.DataFrame(records)
            
            st.subheader(f"📅 Report for {report_date.strftime('%B %d, %Y')}")
            st.dataframe(df, use_container_width=True)
            
            # Statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Records", len(records))
            with col2:
                present = len([r for r in records if r.get('status') == 'PRESENT'])
                st.metric("Present", present)
            with col3:
                absent = len([r for r in records if r.get('status') == 'ABSENT'])
                st.metric("Absent", absent)
            
            # Download options
            if report_type == "CSV Export":
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"attendance_{date_str}.csv",
                    mime="text/csv"
                )
        else:
            st.info("No records found for the selected date and filter")

# Student Attendance Page
elif page == "👤 Student Attendance":
    st.header("👤 Student Attendance History")
    
    # Search student
    search_option = st.radio("Search by", ["Roll Number", "Student ID"])
    
    if search_option == "Roll Number":
        roll_number = st.text_input("Enter Roll Number")
        if st.button("Search"):
            student = st.session_state.db_manager.get_student_by_roll_number(roll_number)
            if student:
                st.session_state.selected_student = student
            else:
                st.error("Student not found")
    else:
        student_id = st.number_input("Enter Student ID", min_value=1)
        if st.button("Search"):
            student = st.session_state.db_manager.get_student_by_id(student_id)
            if student:
                st.session_state.selected_student = student
            else:
                st.error("Student not found")
    
    # Display student info and attendance
    if 'selected_student' in st.session_state:
        student = st.session_state.selected_student
        
        st.subheader("Student Information")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Name:** {student['name']}")
        with col2:
            st.write(f"**Roll Number:** {student['roll_number']}")
        with col3:
            st.write(f"**Subject:** {student['subject']}")
        
        st.divider()
        
        # Get attendance history
        attendance = st.session_state.db_manager.get_student_attendance(student['id'])
        
        if attendance:
            st.subheader("📋 Attendance History")
            df = pd.DataFrame(attendance)
            st.dataframe(df, use_container_width=True)
            
            # Statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Days", len(attendance))
            with col2:
                present = len([a for a in attendance if a.get('status') == 'PRESENT'])
                st.metric("Present", present)
            with col3:
                absent = len([a for a in attendance if a.get('status') == 'ABSENT'])
                st.metric("Absent", absent)
            with col4:
                percentage = (present / len(attendance) * 100) if attendance else 0
                st.metric("Attendance %", f"{percentage:.1f}%")
        else:
            st.info("No attendance records found for this student")

# Footer
st.sidebar.divider()
st.sidebar.info("🎓 Smart Attendance System v1.0")
st.sidebar.caption("Powered by Face Recognition & Deep Learning")
