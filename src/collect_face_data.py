"""
"""
Face Data Collection Module
Captures multiple face images per student with variations for better recognition
"""

import cv2
import os
import time
from datetime import datetime
from . import config
from .database_manager import DatabaseManager
from .encode_faces import FaceEncoder


class FaceDataCollector:
    """Collects face images for students and stores them in organized folders"""
    
    def __init__(self):
        """Initialize face data collector"""
        self.dataset_path = config.DATASET_PATH
        self.images_per_student = config.IMAGES_PER_STUDENT
        self.capture_delay = config.IMAGE_CAPTURE_DELAY
        self.db = DatabaseManager()
        
        # Ensure dataset directory exists
        os.makedirs(self.dataset_path, exist_ok=True)
        
        # Load face detector (using Haar Cascade for speed)
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
    
    def get_student_info(self):
        """Get student information from user input"""
        print("\n" + "="*60)
        print("FACE DATA COLLECTION - STUDENT REGISTRATION")
        print("="*60)
        
        name = input("\nEnter Student Name: ").strip()
        while not name:
            print("Name cannot be empty!")
            name = input("Enter Student Name: ").strip()
        
        roll_number = input("Enter Roll Number: ").strip()
        while not roll_number:
            print("Roll number cannot be empty!")
            roll_number = input("Enter Roll Number: ").strip()
        
        # Generate student ID
        student_id = f"{config.STUDENT_ID_PREFIX}{roll_number.zfill(config.STUDENT_ID_LENGTH)}_{name.replace(' ', '_')}"
        
        return student_id, name, roll_number
    
    def create_student_folder(self, student_id: str) -> str:
        """Create folder for student if it doesn't exist"""
        folder_path = os.path.join(self.dataset_path, student_id)
        
        if os.path.exists(folder_path):
            response = input(f"\nFolder '{student_id}' already exists. Overwrite? (y/n): ")
            if response.lower() != 'y':
                return None
            # Clear existing images
            for file in os.listdir(folder_path):
                os.remove(os.path.join(folder_path, file))
        else:
            os.makedirs(folder_path, exist_ok=True)
        
        return folder_path
    
    def collect_faces(self, student_id: str, name: str, roll_number: str):
        """
        Main function to collect face images
        Captures multiple images with slight variations
        """
        # Create student folder
        folder_path = self.create_student_folder(student_id)
        if not folder_path:
            print("Data collection cancelled.")
            return False
        
        # Register student in database
        self.db.register_student(student_id, name, roll_number)
        
        # Initialize camera
        print("\n" + "-"*60)
        print("Initializing camera...")
        cap = cv2.VideoCapture(config.CAMERA_ENTRY_ID)
        
        if not cap.isOpened():
            print("Error: Could not open camera!")
            return False
        
        # Set camera resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.WINDOW_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.WINDOW_HEIGHT)
        
        print("\n" + "="*60)
        print(f"CAPTURING {self.images_per_student} IMAGES FOR: {name}")
        print("="*60)
        print("\nINSTRUCTIONS:")
        print("  • Look at the camera")
        print("  • Move your head slightly (left, right, up, down)")
        print("  • Try different expressions")
        print("  • Ensure good lighting")
        print("  • Press 'q' to quit anytime")
        print("\n" + "-"*60)
        
        count = 0
        start_time = time.time()
        
        while count < self.images_per_student:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture frame!")
                break
            
            # Convert to grayscale for face detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(100, 100)
            )
            
            # Draw rectangles and capture
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x+w, y+h), config.COLOR_GREEN, 2)
                
                # Capture face region
                face_roi = frame[y:y+h, x:x+w]
                
                # Save image
                img_name = f"img{count+1}.jpg"
                img_path = os.path.join(folder_path, img_name)
                cv2.imwrite(img_path, face_roi)
                
                count += 1
                
                # Show progress
                progress = (count / self.images_per_student) * 100
                print(f"Captured: {count}/{self.images_per_student} [{progress:.1f}%]", end='\r')
                
                # Add delay between captures
                time.sleep(self.capture_delay)
                
                if count >= self.images_per_student:
                    break
            
            # Display instructions on frame
            cv2.putText(frame, f"Images: {count}/{self.images_per_student}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                       config.FONT_SCALE, config.COLOR_GREEN, config.FONT_THICKNESS)
            
            cv2.putText(frame, "Press 'q' to quit", 
                       (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.5, config.COLOR_WHITE, 1)
            
            # Show frame
            cv2.imshow('Face Data Collection', frame)
            
            # Check for quit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\n\nData collection interrupted by user.")
                break
        
        # Cleanup
        cap.release()
        cv2.destroyAllWindows()
        
        elapsed_time = time.time() - start_time
        
        # Summary
        print("\n\n" + "="*60)
        print("DATA COLLECTION COMPLETE!")
        print("="*60)
        print(f"Student ID    : {student_id}")
        print(f"Name          : {name}")
        print(f"Roll Number   : {roll_number}")
        print(f"Images Saved  : {count}")
        print(f"Folder Path   : {folder_path}")
        print(f"Time Taken    : {elapsed_time:.2f} seconds")
        print("="*60)
        
        return count >= self.images_per_student
    
    def run(self):
        """Main entry point for face data collection"""
        try:
            # Get student information
            student_id, name, roll_number = self.get_student_info()
            
            # Collect faces
            success = self.collect_faces(student_id, name, roll_number)
            
            if success:
                print("\n✓ Face data collection successful!")
                print("\n" + "="*60)
                print("ENCODING STUDENT FACES")
                print("="*60)
                
                # Automatically encode only this student's faces
                encoder = FaceEncoder()
                encode_success, num_encoded = encoder.encode_single_student(student_id)
                
                if encode_success:
                    print("\n✓ Student encoding complete!")
                    print(f"  Encoded {num_encoded} face images")
                    print("\n" + "="*60)
                    print("✓ REGISTRATION COMPLETE!")
                    print("="*60)
                    print(f"  Student: {name}")
                    print(f"  Roll Number: {roll_number}")
                    print(f"  Student ID: {student_id}")
                    print("  Status: Ready for attendance tracking")
                    print("="*60)
                else:
                    print("\n⚠️  Warning: Face encoding failed!")
                    print("  You may need to run encode_faces.py manually")
            else:
                print("\n✗ Face data collection incomplete!")
            
        except KeyboardInterrupt:
            print("\n\nData collection interrupted by user.")
        except Exception as e:
            print(f"\n✗ Error during data collection: {e}")


def main():
    """Main function"""
    collector = FaceDataCollector()
    collector.run()


if __name__ == "__main__":
    main()
