"""
Database Manager for Smart Attendance Management System
Handles all database operations including table creation, data insertion, and queries
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Tuple, Optional
from . import config


class DatabaseManager:
    """Manages all database operations for the attendance system"""
    
    def __init__(self):
        """Initialize database connection and create tables if they don't exist"""
        self.db_path = config.DATABASE_FILE
        self._ensure_database_directory()
        self.create_tables()
    
    def _ensure_database_directory(self):
        """Create database directory if it doesn't exist"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path, timeout=config.DB_TIMEOUT)
    
    def create_tables(self):
        """Create necessary database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Students table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                roll_number TEXT UNIQUE NOT NULL,
                registered_date TEXT NOT NULL
            )
        """)
        
        # Entry log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entry_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                name TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                date TEXT NOT NULL,
                status TEXT DEFAULT 'INSIDE',
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        """)
        
        # Exit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                name TEXT NOT NULL,
                entry_id INTEGER NOT NULL,
                exit_time TEXT NOT NULL,
                date TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (entry_id) REFERENCES entry_log(id)
            )
        """)
        
        # Attendance table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                name TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                exit_time TEXT NOT NULL,
                duration INTEGER NOT NULL,
                status TEXT NOT NULL,
                date TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def register_student(self, student_id: str, name: str, roll_number: str) -> bool:
        """Register a new student in the database"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            registered_date = datetime.now().strftime(config.REPORT_DATE_FORMAT)
            
            cursor.execute("""
                INSERT INTO students (student_id, name, roll_number, registered_date)
                VALUES (?, ?, ?, ?)
            """, (student_id, name, roll_number, registered_date))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_student_info(self, student_id: str) -> Optional[Tuple]:
        """Get student information by student_id"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT student_id, name, roll_number, registered_date
            FROM students WHERE student_id = ?
        """, (student_id,))
        
        result = cursor.fetchone()
        conn.close()
        return result
    
    def mark_entry(self, student_id: str, name: str) -> Optional[int]:
        """Mark student entry and return entry_id"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        current_date = datetime.now().strftime(config.REPORT_DATE_FORMAT)
        current_time = datetime.now().strftime(config.REPORT_DATETIME_FORMAT)
        
        # Check if student already has an active entry for today
        cursor.execute("""
            SELECT id FROM entry_log 
            WHERE student_id = ? AND date = ? AND status = 'INSIDE'
        """, (student_id, current_date))
        
        existing_entry = cursor.fetchone()
        
        if existing_entry:
            conn.close()
            return None  # Already inside
        
        # Insert new entry
        cursor.execute("""
            INSERT INTO entry_log (student_id, name, entry_time, date, status)
            VALUES (?, ?, ?, ?, 'INSIDE')
        """, (student_id, name, current_time, current_date))
        
        entry_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return entry_id
    
    def mark_exit(self, student_id: str, name: str) -> Optional[Tuple[int, str, str]]:
        """
        Mark student exit and return (entry_id, entry_time, exit_time)
        Returns None if no active entry found
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        current_date = datetime.now().strftime(config.REPORT_DATE_FORMAT)
        current_time = datetime.now().strftime(config.REPORT_DATETIME_FORMAT)
        
        # Find active entry for today
        cursor.execute("""
            SELECT id, entry_time FROM entry_log
            WHERE student_id = ? AND date = ? AND status = 'INSIDE'
            ORDER BY id DESC LIMIT 1
        """, (student_id, current_date))
        
        entry_record = cursor.fetchone()
        
        if not entry_record:
            conn.close()
            return None  # No active entry found
        
        entry_id, entry_time = entry_record
        
        # Mark entry as exited
        cursor.execute("""
            UPDATE entry_log SET status = 'EXITED'
            WHERE id = ?
        """, (entry_id,))
        
        # Insert exit log
        cursor.execute("""
            INSERT INTO exit_log (student_id, name, entry_id, exit_time, date)
            VALUES (?, ?, ?, ?, ?)
        """, (student_id, name, entry_id, current_time, current_date))
        
        conn.commit()
        conn.close()
        
        return (entry_id, entry_time, current_time)
    
    def save_attendance(self, student_id: str, name: str, entry_time: str, 
                       exit_time: str, duration: int, status: str, date: str) -> bool:
        """Save final attendance record"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO attendance (student_id, name, entry_time, exit_time, 
                                      duration, status, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (student_id, name, entry_time, exit_time, duration, status, date))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving attendance: {e}")
            return False
    
    def get_attendance_by_date(self, date: str) -> List[Tuple]:
        """Get all attendance records for a specific date"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT student_id, name, entry_time, exit_time, duration, status, date
            FROM attendance WHERE date = ?
            ORDER BY entry_time
        """, (date,))
        
        records = cursor.fetchall()
        conn.close()
        return records
    
    def get_all_attendance(self) -> List[Tuple]:
        """Get all attendance records"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT student_id, name, entry_time, exit_time, duration, status, date
            FROM attendance
            ORDER BY date DESC, entry_time DESC
        """)
        
        records = cursor.fetchall()
        conn.close()
        return records
    
    def get_student_attendance(self, student_id: str) -> List[Tuple]:
        """Get all attendance records for a specific student"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT student_id, name, entry_time, exit_time, duration, status, date
            FROM attendance WHERE student_id = ?
            ORDER BY date DESC
        """, (student_id,))
        
        records = cursor.fetchall()
        conn.close()
        return records
    
    def get_all_students(self) -> List[Tuple]:
        """Get all registered students"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT student_id, name, roll_number, registered_date
            FROM students
            ORDER BY student_id
        """)
        
        students = cursor.fetchall()
        conn.close()
        return students
