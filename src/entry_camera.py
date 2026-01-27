"""
Entry Camera System
Detects and recognizes students entering the premises and marks entry time
"""

import cv2
import face_recognition
import pickle
import os
from datetime import datetime
import numpy as np
from . import config
from .database_manager import DatabaseManager


class EntryCameraSystem:
    """Manages entry point face recognition and logging"""
    
    def __init__(self):
        """Initialize entry camera system"""
        self.encodings_file = config.ENCODINGS_FILE
        self.camera_id = config.CAMERA_ENTRY_ID
        self.db = DatabaseManager()
        self.known_encodings = []
        self.known_names = []
        self.tolerance = config.FACE_RECOGNITION_TOLERANCE
        
        # Load encodings
        self.load_encodings()
    
    def load_encodings(self):
        """Load face encodings from pickle file"""
        print("\n" + "="*60)
        print("LOADING FACE ENCODINGS")
        print("="*60)
        
        if not os.path.exists(self.encodings_file):
            print(f"✗ Encodings file not found: {self.encodings_file}")
            print("  Please run 'encode_faces.py' first!")
            return False
        
        try:
            with open(self.encodings_file, 'rb') as f:
                data = pickle.load(f)
            
            self.known_encodings = data["encodings"]
            self.known_names = data["names"]
            
            unique_students = len(set(self.known_names))
            print(f"✓ Loaded {len(self.known_encodings)} encodings for {unique_students} students")
            return True
            
        except Exception as e:
            print(f"✗ Error loading encodings: {e}")
            return False
    
    def recognize_face(self, frame):
        """
        Recognize face in the given frame
        Returns (student_id, confidence) or (None, 0) if no match
        """
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Detect face locations
        face_locations = face_recognition.face_locations(
            rgb_frame, 
            model=config.FACE_DETECTION_MODEL
        )
        
        if not face_locations:
            return None, 0
        
        # Generate encodings for detected faces
        face_encodings = face_recognition.face_encodings(
            rgb_frame, 
            face_locations,
            model=config.FACE_ENCODING_MODEL
        )
        
        # Check each detected face
        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            # Compare with known faces
            matches = face_recognition.compare_faces(
                self.known_encodings, 
                face_encoding,
                tolerance=self.tolerance
            )
            
            # Calculate face distances
            face_distances = face_recognition.face_distance(
                self.known_encodings, 
                face_encoding
            )
            
            student_id = "Unknown"
            confidence = 0
            
            if True in matches:
                # Find best match
                best_match_index = np.argmin(face_distances)
                
                if matches[best_match_index]:
                    student_id = self.known_names[best_match_index]
                    # Convert distance to confidence (0-100%)
                    confidence = (1 - face_distances[best_match_index]) * 100
                    
                    return student_id, confidence, (top, right, bottom, left)
        
        return None, 0, None
    
    def run(self):
        """Main entry point for entry camera system"""
        print("\n" + "╔" + "="*58 + "╗")
        print("║" + " "*15 + "ENTRY CAMERA SYSTEM" + " "*24 + "║")
        print("╚" + "="*58 + "╝")
        
        if not self.known_encodings:
            print("\n✗ No encodings loaded. Cannot start entry system.")
            return
        
        # Initialize camera
        print("\nInitializing camera...")
        cap = cv2.VideoCapture(self.camera_id)
        
        if not cap.isOpened():
            print("✗ Error: Could not open camera!")
            return
        
        # Set camera resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.WINDOW_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.WINDOW_HEIGHT)
        
        print("✓ Camera initialized successfully")
        print("\n" + "="*60)
        print("SYSTEM ACTIVE - Monitoring Entry Point")
        print("="*60)
        print("Instructions:")
        print("  • Stand in front of camera")
        print("  • Wait for recognition")
        print("  • Press 'q' to quit")
        print("  • Press 's' to skip frame")
        print("="*60 + "\n")
        
        last_recognized = None
        recognition_cooldown = 0
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("✗ Error: Failed to capture frame!")
                    break
                
                # Reduce cooldown
                if recognition_cooldown > 0:
                    recognition_cooldown -= 1
                
                # Recognize face
                result = self.recognize_face(frame)
                
                if result[0] and recognition_cooldown == 0:
                    student_id, confidence, bbox = result
                    
                    # Only process if different from last or cooldown expired
                    if student_id != last_recognized:
                        # Extract name from student_id
                        name_parts = student_id.split('_')
                        if len(name_parts) >= 3:
                            name = '_'.join(name_parts[2:])
                        else:
                            name = student_id
                        
                        # Mark entry in database
                        entry_id = self.db.mark_entry(student_id, name)
                        
                        if entry_id:
                            current_time = datetime.now().strftime(config.REPORT_DATETIME_FORMAT)
                            print(f"\n{'='*60}")
                            print(f"✓ ENTRY MARKED")
                            print(f"{'='*60}")
                            print(f"  Student ID  : {student_id}")
                            print(f"  Name        : {name}")
                            print(f"  Time        : {current_time}")
                            print(f"  Confidence  : {confidence:.2f}%")
                            print(f"  Entry ID    : {entry_id}")
                            print(f"{'='*60}\n")
                            
                            last_recognized = student_id
                            recognition_cooldown = 30  # ~1 second cooldown at 30fps
                        else:
                            print(f"\n⚠ {name} already inside (Entry not marked)")
                            recognition_cooldown = 15
                    
                    # Draw bounding box and label
                    top, right, bottom, left = bbox
                    cv2.rectangle(frame, (left, top), (right, bottom), config.COLOR_GREEN, 2)
                    
                    # Draw label
                    name_parts = student_id.split('_')
                    display_name = '_'.join(name_parts[2:]) if len(name_parts) >= 3 else student_id
                    label = f"{display_name} ({confidence:.1f}%)"
                    
                    cv2.rectangle(frame, (left, bottom - 35), (right, bottom), 
                                config.COLOR_GREEN, cv2.FILLED)
                    cv2.putText(frame, label, (left + 6, bottom - 6),
                              cv2.FONT_HERSHEY_DUPLEX, 0.5, config.COLOR_WHITE, 1)
                
                # Display status
                status = "READY - Waiting for face..."
                cv2.putText(frame, status, (10, 30),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, config.COLOR_GREEN, 2)
                
                # Display instructions
                cv2.putText(frame, "Press 'q' to quit", (10, frame.shape[0] - 10),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, config.COLOR_WHITE, 1)
                
                # Show frame
                cv2.imshow('Entry Camera System', frame)
                
                # Check for key press
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\n✓ Entry system stopped by user.")
                    break
                elif key == ord('s'):
                    last_recognized = None
                    recognition_cooldown = 0
                    print("  Skipped - Ready for next recognition")
        
        except KeyboardInterrupt:
            print("\n\n✓ Entry system interrupted by user.")
        
        finally:
            # Cleanup
            cap.release()
            cv2.destroyAllWindows()
            print("\n" + "="*60)
            print("ENTRY CAMERA SYSTEM CLOSED")
            print("="*60)


def main():
    """Main function"""
    entry_system = EntryCameraSystem()
    entry_system.run()


if __name__ == "__main__":
    main()
