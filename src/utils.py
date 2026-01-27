"""
Utility Functions
Report generation, logging, and helper functions
"""

import os
import csv
import logging
from datetime import datetime
from typing import List, Tuple
from . import config
from .database_manager import DatabaseManager


class ReportGenerator:
    """Generates attendance reports in various formats"""
    
    def __init__(self):
        """Initialize report generator"""
        self.db = DatabaseManager()
        self.reports_path = config.REPORTS_PATH
        
        # Ensure reports directory exists
        os.makedirs(self.reports_path, exist_ok=True)
    
    def generate_csv_report(self, date: str = None, filename: str = None) -> str:
        """
        Generate CSV report for attendance
        
        Args:
            date: Specific date (YYYY-MM-DD) or None for all records
            filename: Custom filename or None for auto-generated
        
        Returns:
            Path to generated report file
        """
        # Get attendance records
        if date:
            records = self.db.get_attendance_by_date(date)
            if not filename:
                filename = f"attendance_report_{date}.csv"
        else:
            records = self.db.get_all_attendance()
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"attendance_report_all_{timestamp}.csv"
        
        # Create report file path
        report_path = os.path.join(self.reports_path, filename)
        
        # Write CSV file
        with open(report_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([
                'Student ID', 'Name', 'Entry Time', 'Exit Time', 
                'Duration (min)', 'Status', 'Date'
            ])
            
            # Write records
            for record in records:
                writer.writerow(record)
        
        return report_path
    
    def generate_daily_report(self, date: str = None) -> str:
        """
        Generate detailed daily attendance report
        
        Args:
            date: Date in YYYY-MM-DD format or None for today
        
        Returns:
            Path to generated report file
        """
        if not date:
            date = datetime.now().strftime(config.REPORT_DATE_FORMAT)
        
        records = self.db.get_attendance_by_date(date)
        
        # Create report filename
        filename = f"daily_report_{date}.txt"
        report_path = os.path.join(self.reports_path, filename)
        
        # Calculate statistics
        total_students = len(records)
        present_count = sum(1 for r in records if r[5] == "PRESENT")
        absent_count = sum(1 for r in records if r[5] == "ABSENT")
        
        # Write report
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write(" " * 15 + "DAILY ATTENDANCE REPORT\n")
            f.write("="*70 + "\n\n")
            f.write(f"Date: {date}\n")
            f.write(f"Generated: {datetime.now().strftime(config.REPORT_DATETIME_FORMAT)}\n\n")
            f.write("-"*70 + "\n")
            f.write("SUMMARY\n")
            f.write("-"*70 + "\n")
            f.write(f"Total Students    : {total_students}\n")
            f.write(f"Present           : {present_count}\n")
            f.write(f"Absent            : {absent_count}\n")
            
            if total_students > 0:
                attendance_rate = (present_count / total_students) * 100
                f.write(f"Attendance Rate   : {attendance_rate:.2f}%\n")
            
            f.write("\n" + "="*70 + "\n")
            f.write("DETAILED RECORDS\n")
            f.write("="*70 + "\n\n")
            
            # Write header
            f.write(f"{'Student ID':<25} {'Name':<20} {'Entry':<10} {'Exit':<10} {'Duration':<10} {'Status':<10}\n")
            f.write("-"*70 + "\n")
            
            # Write records
            for record in records:
                student_id, name, entry_time, exit_time, duration, status, _ = record
                
                # Extract time only
                entry_time_only = entry_time.split()[1] if ' ' in entry_time else entry_time
                exit_time_only = exit_time.split()[1] if ' ' in exit_time else exit_time
                
                f.write(f"{student_id:<25} {name:<20} {entry_time_only:<10} {exit_time_only:<10} {duration:<10} {status:<10}\n")
            
            f.write("\n" + "="*70 + "\n")
            f.write("END OF REPORT\n")
            f.write("="*70 + "\n")
        
        return report_path
    
    def generate_student_report(self, student_id: str) -> str:
        """
        Generate attendance report for a specific student
        
        Args:
            student_id: Student ID
        
        Returns:
            Path to generated report file
        """
        records = self.db.get_student_attendance(student_id)
        
        if not records:
            print(f"No attendance records found for {student_id}")
            return None
        
        # Get student info
        student_info = self.db.get_student_info(student_id)
        
        # Create report filename
        filename = f"student_report_{student_id}.txt"
        report_path = os.path.join(self.reports_path, filename)
        
        # Calculate statistics
        total_days = len(records)
        present_days = sum(1 for r in records if r[5] == "PRESENT")
        absent_days = sum(1 for r in records if r[5] == "ABSENT")
        total_duration = sum(r[4] for r in records)
        avg_duration = total_duration / total_days if total_days > 0 else 0
        
        # Write report
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write(" " * 15 + "STUDENT ATTENDANCE REPORT\n")
            f.write("="*70 + "\n\n")
            
            if student_info:
                f.write(f"Student ID      : {student_info[0]}\n")
                f.write(f"Name            : {student_info[1]}\n")
                f.write(f"Roll Number     : {student_info[2]}\n")
                f.write(f"Registered Date : {student_info[3]}\n\n")
            
            f.write("-"*70 + "\n")
            f.write("SUMMARY\n")
            f.write("-"*70 + "\n")
            f.write(f"Total Days        : {total_days}\n")
            f.write(f"Present           : {present_days}\n")
            f.write(f"Absent            : {absent_days}\n")
            f.write(f"Average Duration  : {avg_duration:.2f} minutes\n")
            
            if total_days > 0:
                attendance_rate = (present_days / total_days) * 100
                f.write(f"Attendance Rate   : {attendance_rate:.2f}%\n")
            
            f.write("\n" + "="*70 + "\n")
            f.write("ATTENDANCE HISTORY\n")
            f.write("="*70 + "\n\n")
            
            # Write header
            f.write(f"{'Date':<15} {'Entry Time':<12} {'Exit Time':<12} {'Duration':<12} {'Status':<10}\n")
            f.write("-"*70 + "\n")
            
            # Write records
            for record in records:
                _, _, entry_time, exit_time, duration, status, date = record
                
                # Extract time only
                entry_time_only = entry_time.split()[1] if ' ' in entry_time else entry_time
                exit_time_only = exit_time.split()[1] if ' ' in exit_time else exit_time
                
                f.write(f"{date:<15} {entry_time_only:<12} {exit_time_only:<12} {duration:<12} {status:<10}\n")
            
            f.write("\n" + "="*70 + "\n")
            f.write("END OF REPORT\n")
            f.write("="*70 + "\n")
        
        return report_path
    
    def print_summary(self):
        """Print attendance summary to console"""
        today = datetime.now().strftime(config.REPORT_DATE_FORMAT)
        records = self.db.get_attendance_by_date(today)
        
        print("\n" + "="*60)
        print(f"ATTENDANCE SUMMARY - {today}")
        print("="*60)
        
        if not records:
            print("No attendance records for today.")
        else:
            present = sum(1 for r in records if r[5] == "PRESENT")
            absent = sum(1 for r in records if r[5] == "ABSENT")
            total = len(records)
            
            print(f"Total Students: {total}")
            print(f"Present: {present}")
            print(f"Absent: {absent}")
            print(f"Attendance Rate: {(present/total)*100:.2f}%")
        
        print("="*60)


class Logger:
    """System logger for tracking events"""
    
    def __init__(self):
        """Initialize logger"""
        self.log_file = config.LOG_FILE
        
        # Ensure logs directory exists
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, config.LOG_LEVEL),
            format=config.LOG_FORMAT,
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error message"""
        self.logger.error(message)
    
    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)


def display_menu():
    """Display main menu"""
    print("\n" + "╔" + "="*58 + "╗")
    print("║" + " "*8 + "SMART ATTENDANCE MANAGEMENT SYSTEM" + " "*16 + "║")
    print("╚" + "="*58 + "╝")
    print("\nMAIN MENU:")
    print("  1. Collect Face Data (Register Student)")
    print("  2. Generate Face Encodings")
    print("  3. Run Entry Camera System")
    print("  4. Run Exit Camera System")
    print("  5. Generate Today's Report")
    print("  6. Generate All Attendance Report")
    print("  7. Generate Student Report")
    print("  8. View Attendance Summary")
    print("  9. Exit")
    print("\n" + "="*60)
