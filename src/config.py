"""
Configuration file for Smart Attendance Management System
All system parameters and settings are defined here
"""

import os

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATASET_PATH = os.path.join(DATA_DIR, "dataset")
ENCODINGS_PATH = os.path.join(DATA_DIR, "encodings")
DATABASE_PATH = os.path.join(DATA_DIR, "database")
LOGS_PATH = os.path.join(DATA_DIR, "logs")
REPORTS_PATH = os.path.join(DATA_DIR, "reports")

# File paths
ENCODINGS_FILE = os.path.join(ENCODINGS_PATH, "face_encodings.pkl")
DATABASE_FILE = os.path.join(DATABASE_PATH, "attendance.db")
LOG_FILE = os.path.join(LOGS_PATH, "system_logs.txt")

# Camera settings
CAMERA_ENTRY_ID = 0  # Camera index for entry point
CAMERA_EXIT_ID = 0   # Camera index for exit point (change to 1 if using separate camera)

# Face recognition settings
FACE_DETECTION_MODEL = "hog"  # Options: "hog" (faster, CPU) or "cnn" (accurate, GPU)
FACE_RECOGNITION_TOLERANCE = 0.6  # Lower = stricter (0.6 is default)
FACE_ENCODING_MODEL = "large"  # Options: "small" or "large"

# Data collection settings
IMAGES_PER_STUDENT = 20  # Number of face samples to collect per student
IMAGE_CAPTURE_DELAY = 0.1  # Delay between captures in seconds

# Attendance settings
MINIMUM_DURATION = 2  # Minimum duration in minutes to mark present (TESTING MODE: 2 mins)
MAX_RECOGNITION_ATTEMPTS = 3  # Maximum attempts for face recognition

# Display settings
WINDOW_WIDTH = 640
WINDOW_HEIGHT = 480
FONT_SCALE = 0.7
FONT_THICKNESS = 2

# Colors (BGR format for OpenCV)
COLOR_GREEN = (0, 255, 0)
COLOR_RED = (0, 0, 255)
COLOR_BLUE = (255, 0, 0)
COLOR_WHITE = (255, 255, 255)

# Student ID format
STUDENT_ID_PREFIX = "student_"
STUDENT_ID_LENGTH = 3  # e.g., 001, 002, 003

# Database settings
DB_TIMEOUT = 10  # Database connection timeout in seconds

# Logging settings
LOG_LEVEL = "INFO"  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# Report settings
REPORT_DATE_FORMAT = "%Y-%m-%d"
REPORT_TIME_FORMAT = "%H:%M:%S"
REPORT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
