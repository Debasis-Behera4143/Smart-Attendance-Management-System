"""
Flask Web Application for Smart Attendance Management System
Web interface for face recognition-based attendance
"""

from flask import Flask, render_template, request, jsonify, send_file, Response
import cv2
import os
import sys
import json
from datetime import datetime
import base64
import numpy as np
from io import BytesIO
from PIL import Image

# Add parent directory to path to import src modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database_manager import DatabaseManager
from src.collect_face_data import FaceDataCollector
from src.encode_faces import FaceEncoder
from src.utils import ReportGenerator
from src.attendance_manager import AttendanceManager
import src.config as config

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Initialize components
db = DatabaseManager()
report_gen = ReportGenerator()
attendance_mgr = AttendanceManager()


@app.route('/')
def index():
    """Home page - redirect to dashboard"""
    return render_template('dashboard.html')


@app.route('/dashboard')
def dashboard():
    """Dashboard page"""
    # Get today's statistics
    today = datetime.now().strftime(config.REPORT_DATE_FORMAT)
    records = db.get_attendance_by_date(today)
    
    total = len(records)
    present = sum(1 for r in records if r[5] == "PRESENT")
    absent = sum(1 for r in records if r[5] == "ABSENT")
    
    stats = {
        'total': total,
        'present': present,
        'absent': absent,
        'attendance_rate': round((present / total * 100), 2) if total > 0 else 0,
        'date': today
    }
    
    return render_template('dashboard.html', stats=stats, records=records)


@app.route('/register')
def register_page():
    """Student registration page"""
    return render_template('register.html')


@app.route('/entry')
def entry_page():
    """Entry camera page"""
    return render_template('entry.html')


@app.route('/exit')
def exit_page():
    """Exit camera page"""
    return render_template('exit.html')


@app.route('/reports')
def reports_page():
    """Reports page"""
    all_records = db.get_all_attendance()
    students = db.get_all_students()
    return render_template('reports.html', records=all_records, students=students)


@app.route('/api/register-student', methods=['POST'])
def register_student():
    """API endpoint to register a new student"""
    try:
        data = request.json
        student_id = data.get('student_id')
        name = data.get('name')
        roll_number = data.get('roll_number')
        
        # Register in database
        success = db.register_student(student_id, name, roll_number)
        
        if success:
            return jsonify({'success': True, 'message': 'Student registered successfully'})
        else:
            return jsonify({'success': False, 'message': 'Student already exists'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/save-face-images', methods=['POST'])
def save_face_images():
    """API endpoint to save captured face images"""
    try:
        data = request.json
        student_id = data.get('student_id')
        images = data.get('images')  # Base64 encoded images
        
        # Create student folder
        folder_path = os.path.join(config.DATASET_PATH, student_id)
        os.makedirs(folder_path, exist_ok=True)
        
        # Save images
        for i, img_data in enumerate(images):
            # Remove header from base64 string
            img_data = img_data.split(',')[1] if ',' in img_data else img_data
            
            # Decode base64 to image
            img_bytes = base64.b64decode(img_data)
            img = Image.open(BytesIO(img_bytes))
            
            # Save image
            img_path = os.path.join(folder_path, f'img{i+1}.jpg')
            img.save(img_path, 'JPEG')
        
        return jsonify({'success': True, 'message': f'Saved {len(images)} images'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/generate-encodings', methods=['POST'])
def generate_encodings():
    """API endpoint to generate face encodings"""
    try:
        encoder = FaceEncoder()
        success = encoder.run()
        
        if success:
            return jsonify({'success': True, 'message': 'Encodings generated successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to generate encodings'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/mark-entry', methods=['POST'])
def mark_entry():
    """API endpoint to mark student entry"""
    try:
        data = request.json
        student_id = data.get('student_id')
        name = data.get('name')
        
        entry_id = db.mark_entry(student_id, name)
        
        if entry_id:
            current_time = datetime.now().strftime(config.REPORT_DATETIME_FORMAT)
            return jsonify({
                'success': True,
                'message': 'Entry marked successfully',
                'entry_id': entry_id,
                'time': current_time
            })
        else:
            return jsonify({'success': False, 'message': 'Already inside'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/mark-exit', methods=['POST'])
def mark_exit():
    """API endpoint to mark student exit"""
    try:
        data = request.json
        student_id = data.get('student_id')
        name = data.get('name')
        
        exit_data = db.mark_exit(student_id, name)
        
        if exit_data:
            entry_id, entry_time, exit_time = exit_data
            
            # Calculate attendance
            attendance_result = attendance_mgr.calculate_attendance(
                student_id, name, entry_time, exit_time
            )
            
            if attendance_result:
                duration, status, date = attendance_result
                
                # Save attendance
                db.save_attendance(
                    student_id, name, entry_time, exit_time,
                    duration, status, date
                )
                
                return jsonify({
                    'success': True,
                    'message': 'Exit marked successfully',
                    'entry_time': entry_time,
                    'exit_time': exit_time,
                    'duration': duration,
                    'status': status
                })
        else:
            return jsonify({'success': False, 'message': 'No active entry found'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/get-students')
def get_students():
    """API endpoint to get all students"""
    try:
        students = db.get_all_students()
        student_list = [{
            'student_id': s[0],
            'name': s[1],
            'roll_number': s[2],
            'registered_date': s[3]
        } for s in students]
        
        return jsonify({'success': True, 'students': student_list})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/get-today-attendance')
def get_today_attendance():
    """API endpoint to get today's attendance"""
    try:
        today = datetime.now().strftime(config.REPORT_DATE_FORMAT)
        records = db.get_attendance_by_date(today)
        
        attendance_list = [{
            'student_id': r[0],
            'name': r[1],
            'entry_time': r[2],
            'exit_time': r[3],
            'duration': r[4],
            'status': r[5],
            'date': r[6]
        } for r in records]
        
        return jsonify({'success': True, 'attendance': attendance_list})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/generate-report', methods=['POST'])
def api_generate_report():
    """API endpoint to generate report"""
    try:
        data = request.json
        report_type = data.get('type', 'daily')
        date = data.get('date')
        
        if report_type == 'daily':
            report_path = report_gen.generate_daily_report(date)
        else:
            report_path = report_gen.generate_csv_report(date)
        
        return jsonify({
            'success': True,
            'message': 'Report generated successfully',
            'path': report_path
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


if __name__ == '__main__':
    # Ensure all directories exist
    os.makedirs(config.DATASET_PATH, exist_ok=True)
    os.makedirs(config.ENCODINGS_PATH, exist_ok=True)
    os.makedirs(config.DATABASE_PATH, exist_ok=True)
    os.makedirs(config.LOGS_PATH, exist_ok=True)
    os.makedirs(config.REPORTS_PATH, exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
