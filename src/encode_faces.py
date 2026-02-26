"""
Face Encoding Module
Converts face images into numerical embeddings for recognition
"""

import face_recognition
import pickle
import os
from pathlib import Path
import cv2
from . import config


class FaceEncoder:
    """Generates and saves face encodings from dataset"""
    
    def __init__(self):
        """Initialize face encoder"""
        self.dataset_path = config.DATASET_PATH
        self.encodings_file = config.ENCODINGS_FILE
        self.encoding_model = config.FACE_ENCODING_MODEL
        self.known_encodings = []
        self.known_names = []
        
        # Ensure encodings directory exists
        os.makedirs(os.path.dirname(self.encodings_file), exist_ok=True)
    
    def load_dataset(self):
        """
        Load all images from dataset folder
        Returns list of (image_path, student_id, name)
        """
        print("\n" + "="*60)
        print("LOADING DATASET")
        print("="*60)
        
        image_paths = []
        
        if not os.path.exists(self.dataset_path):
            print(f"Error: Dataset path '{self.dataset_path}' does not exist!")
            return image_paths
        
        # Iterate through student folders
        for student_folder in os.listdir(self.dataset_path):
            folder_path = os.path.join(self.dataset_path, student_folder)
            
            if not os.path.isdir(folder_path):
                continue
            
            # Extract student_id and name from folder name
            # Format: student_001_Debasis
            student_id = student_folder
            
            # Get all image files in folder
            for img_file in os.listdir(folder_path):
                if img_file.lower().endswith(('.jpg', '.jpeg', '.png')):
                    img_path = os.path.join(folder_path, img_file)
                    image_paths.append((img_path, student_id, student_folder))
        
        print(f"Found {len(image_paths)} images across {len(os.listdir(self.dataset_path))} students")
        return image_paths
    
    def encode_faces(self):
        """
        Process all images and generate face encodings
        """
        print("\n" + "="*60)
        print("GENERATING FACE ENCODINGS")
        print("="*60)
        print(f"Encoding Model: {self.encoding_model}")
        print("-"*60)
        
        # Load dataset
        image_paths = self.load_dataset()
        
        if not image_paths:
            print("No images found in dataset!")
            return False
        
        total_images = len(image_paths)
        processed = 0
        failed = 0
        
        # Process each image
        for img_path, student_id, student_name in image_paths:
            try:
                # Load image
                image = face_recognition.load_image_file(img_path)
                
                # Detect face locations
                face_locations = face_recognition.face_locations(
                    image, 
                    model=config.FACE_DETECTION_MODEL,
                    number_of_times_to_upsample=1 if config.FACE_DETECTION_MODEL == "hog" else 2
                )
                
                # Generate encodings
                encodings = face_recognition.face_encodings(
                    image, 
                    face_locations,
                    model=self.encoding_model
                )
                
                if len(encodings) > 0:
                    # If multiple faces detected, use the largest one (likely the main subject)
                    if len(encodings) > 1:
                        # Find largest face by area
                        areas = [(bottom - top) * (right - left) for top, right, bottom, left in face_locations]
                        largest_idx = areas.index(max(areas))
                        self.known_encodings.append(encodings[largest_idx])
                        print(f"  ! Multiple faces ({len(encodings)}) in {os.path.basename(img_path)} - using largest")
                    else:
                        self.known_encodings.append(encodings[0])
                    self.known_names.append(student_id)
                    processed += 1
                else:
                    failed += 1
                    print(f"  ✗ No face detected in: {os.path.basename(img_path)}")
                
                # Progress indicator
                progress = (processed + failed) / total_images * 100
                print(f"Processing: {processed + failed}/{total_images} [{progress:.1f}%] - Success: {processed}, Failed: {failed}", end='\r')
                
            except Exception as e:
                failed += 1
                print(f"\n  ✗ Error processing {img_path}: {e}")
        
        print("\n" + "-"*60)
        print(f"Encoding complete: {processed} successful, {failed} failed")
        
        return processed > 0
    
    def save_encodings(self):
        """Save encodings to pickle file"""
        print("\n" + "="*60)
        print("SAVING ENCODINGS")
        print("="*60)
        
        data = {
            "encodings": self.known_encodings,
            "names": self.known_names
        }
        
        try:
            with open(self.encodings_file, 'wb') as f:
                pickle.dump(data, f)
            
            print(f"✓ Encodings saved successfully!")
            print(f"  File: {self.encodings_file}")
            print(f"  Total encodings: {len(self.known_encodings)}")
            print(f"  Unique students: {len(set(self.known_names))}")
            return True
            
        except Exception as e:
            print(f"✗ Error saving encodings: {e}")
            return False
    
    def run(self):
        """Main entry point for face encoding"""
        print("\n" + "╔" + "="*58 + "╗")
        print("║" + " "*12 + "FACE ENCODING GENERATION" + " "*22 + "║")
        print("╚" + "="*58 + "╝")
        
        # Check if dataset exists
        if not os.path.exists(self.dataset_path):
            print(f"\n✗ Dataset folder not found: {self.dataset_path}")
            print("  Please run 'collect_face_data.py' first!")
            return False
        
        # Encode faces
        success = self.encode_faces()
        
        if not success:
            print("\n✗ Face encoding failed!")
            return False
        
        # Save encodings
        save_success = self.save_encodings()
        
        if save_success:
            print("\n" + "="*60)
            print("✓ ENCODING PROCESS COMPLETE!")
            print("="*60)
            print("  Next step: Run entry/exit camera systems")
            print("="*60)
            return True
        else:
            return False


def main():
    """Main function"""
    encoder = FaceEncoder()
    encoder.run()


if __name__ == "__main__":
    main()
