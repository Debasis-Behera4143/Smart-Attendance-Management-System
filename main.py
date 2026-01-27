"""
Main Controller for Smart Attendance Management System
Provides menu-driven interface to access all system functionalities
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.collect_face_data import FaceDataCollector
from src.encode_faces import FaceEncoder
from src.entry_camera import EntryCameraSystem
from src.exit_camera import ExitCameraSystem
from src.utils import ReportGenerator, display_menu
from src.database_manager import DatabaseManager


class AttendanceSystemController:
    """Main controller for the attendance management system"""
    
    def __init__(self):
        """Initialize the controller"""
        self.running = True
        self.report_gen = ReportGenerator()
        self.db = DatabaseManager()
    
    def collect_face_data(self):
        """Option 1: Collect face data"""
        print("\n" + ">"*60)
        print("STARTING FACE DATA COLLECTION")
        print(">"*60)
        
        collector = FaceDataCollector()
        collector.run()
    
    def generate_encodings(self):
        """Option 2: Generate face encodings"""
        print("\n" + ">"*60)
        print("STARTING FACE ENCODING GENERATION")
        print(">"*60)
        
        encoder = FaceEncoder()
        encoder.run()
    
    def run_entry_camera(self):
        """Option 3: Run entry camera system"""
        print("\n" + ">"*60)
        print("STARTING ENTRY CAMERA SYSTEM")
        print(">"*60)
        
        entry_system = EntryCameraSystem()
        entry_system.run()
    
    def run_exit_camera(self):
        """Option 4: Run exit camera system"""
        print("\n" + ">"*60)
        print("STARTING EXIT CAMERA SYSTEM")
        print(">"*60)
        
        exit_system = ExitCameraSystem()
        exit_system.run()
    
    def generate_daily_report(self):
        """Option 5: Generate today's report"""
        print("\n" + ">"*60)
        print("GENERATING DAILY REPORT")
        print(">"*60)
        
        from datetime import datetime
        
        date_input = input("\nEnter date (YYYY-MM-DD) or press Enter for today: ").strip()
        
        if not date_input:
            date = datetime.now().strftime("%Y-%m-%d")
        else:
            date = date_input
        
        try:
            # Generate daily report
            report_path = self.report_gen.generate_daily_report(date)
            print(f"\n✓ Daily report generated successfully!")
            print(f"  Report saved to: {report_path}")
            
            # Also generate CSV
            csv_path = self.report_gen.generate_csv_report(date)
            print(f"  CSV report saved to: {csv_path}")
            
        except Exception as e:
            print(f"\n✗ Error generating report: {e}")
    
    def generate_all_report(self):
        """Option 6: Generate report for all attendance"""
        print("\n" + ">"*60)
        print("GENERATING COMPLETE ATTENDANCE REPORT")
        print(">"*60)
        
        try:
            csv_path = self.report_gen.generate_csv_report()
            print(f"\n✓ Complete report generated successfully!")
            print(f"  Report saved to: {csv_path}")
            
        except Exception as e:
            print(f"\n✗ Error generating report: {e}")
    
    def generate_student_report(self):
        """Option 7: Generate student-specific report"""
        print("\n" + ">"*60)
        print("GENERATING STUDENT REPORT")
        print(">"*60)
        
        # Show all students
        students = self.db.get_all_students()
        
        if not students:
            print("\n✗ No students registered in the system.")
            return
        
        print("\nRegistered Students:")
        print("-" * 60)
        for i, student in enumerate(students, 1):
            student_id, name, roll_number, reg_date = student
            print(f"{i}. {student_id} - {name} (Roll: {roll_number})")
        print("-" * 60)
        
        student_id = input("\nEnter Student ID: ").strip()
        
        if not student_id:
            print("✗ Invalid student ID")
            return
        
        try:
            report_path = self.report_gen.generate_student_report(student_id)
            
            if report_path:
                print(f"\n✓ Student report generated successfully!")
                print(f"  Report saved to: {report_path}")
            else:
                print("\n✗ No attendance records found for this student.")
                
        except Exception as e:
            print(f"\n✗ Error generating report: {e}")
    
    def view_summary(self):
        """Option 8: View attendance summary"""
        print("\n" + ">"*60)
        print("ATTENDANCE SUMMARY")
        print(">"*60)
        
        self.report_gen.print_summary()
    
    def exit_system(self):
        """Option 9: Exit the system"""
        print("\n" + "="*60)
        print("THANK YOU FOR USING SMART ATTENDANCE SYSTEM")
        print("="*60)
        self.running = False
    
    def handle_choice(self, choice: str):
        """Handle user menu choice"""
        options = {
            '1': self.collect_face_data,
            '2': self.generate_encodings,
            '3': self.run_entry_camera,
            '4': self.run_exit_camera,
            '5': self.generate_daily_report,
            '6': self.generate_all_report,
            '7': self.generate_student_report,
            '8': self.view_summary,
            '9': self.exit_system
        }
        
        if choice in options:
            options[choice]()
        else:
            print("\n✗ Invalid choice! Please select 1-9.")
    
    def run(self):
        """Main program loop"""
        print("\n" + "╔" + "="*58 + "╗")
        print("║" + " "*5 + "WELCOME TO SMART ATTENDANCE MANAGEMENT SYSTEM" + " "*7 + "║")
        print("╚" + "="*58 + "╝")
        
        while self.running:
            try:
                display_menu()
                choice = input("Enter your choice (1-9): ").strip()
                self.handle_choice(choice)
                
                if self.running:
                    input("\nPress Enter to continue...")
                
            except KeyboardInterrupt:
                print("\n\n✓ System interrupted by user.")
                self.exit_system()
            except Exception as e:
                print(f"\n✗ An error occurred: {e}")
                import traceback
                traceback.print_exc()


def main():
    """Main entry point"""
    controller = AttendanceSystemController()
    controller.run()


if __name__ == "__main__":
    main()
