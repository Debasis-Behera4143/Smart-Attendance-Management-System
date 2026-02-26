# Smart Attendance Source Code Guide

This file explains what each module in `src/` does, how data flows through the system, the core logic in each file, and which libraries are used.

## 1. System Architecture at a Glance

The project has three layers:

1. Core source layer (`src/`)
2. Web/API layer (`web/`)
3. Data layer (`data/`, SQLite + image dataset + reports)

Main flow:

1. Register student and collect face images
2. Generate face encodings from dataset images
3. Recognize student at entry and mark entry
4. Recognize student at exit and compute attendance
5. Store and view subject-wise attendance
6. Generate reports for teachers and subject summaries for students

## 2. Modules in `src/`

## `src/config.py`

Purpose:

- Central configuration module for paths, runtime settings, security, recognition parameters, subjects, and reporting formats.

Core logic:

- Uses helper functions `_env_bool`, `_env_int`, `_env_float` to safely parse environment variables with defaults.
- Defines all absolute paths for:
  - dataset images
  - encodings file
  - SQLite database
  - logs
  - reports
- Defines attendance subjects:
  - Operating System
  - Compiler Design
  - ESSP
  - Data Science
  - Machine Learning
- Defines teacher camera modes:
  - `once`
  - `session`
  - `interval`
- Defines recognition controls (tolerance, frame scale, optional YOLO).

Libraries used:

- `os`

## `src/database_manager.py`

Purpose:

- Single database access layer for all student, entry, exit, attendance, analytics, and settings operations.

Core logic:

- Uses SQLite with:
  - foreign keys ON
  - WAL journal mode
  - NORMAL synchronous mode
- Creates and migrates tables:
  - `students`
  - `entry_log`
  - `exit_log`
  - `attendance`
  - `system_settings`
- Adds indexes for faster queries and uniqueness constraints.
- Stores default runtime settings (camera policy, run mode, active subject, YOLO usage).
- Entry/exit transaction logic:
  - `mark_entry`: writes INSIDE record
  - `mark_exit_and_save_attendance`: atomically updates INSIDE to EXITED, writes `exit_log`, calculates duration, writes `attendance`
- Provides filtered and paginated attendance APIs.
- Provides student subject summary and analytics for reports/dashboard.

Important data rules:

- At most one INSIDE entry per student per date (unique partial index).
- Attendance row uniqueness: `(student_id, date, entry_time)`.
- Attendance status only `PRESENT` or `ABSENT`.

Libraries used:

- `sqlite3`
- `datetime`
- `logging`
- `os`
- `typing`

## `src/attendance_manager.py`

Purpose:

- Attendance duration and status calculation rules.

Core logic:

- Parses timestamps using configured datetime format.
- Validates exit time is not earlier than entry time.
- Calculates minutes between entry and exit.
- Assigns status:
  - `PRESENT` if duration >= minimum duration
  - `ABSENT` otherwise
- Provides formatted duration and summary metadata helpers.

Libraries used:

- `datetime`
- `typing`

## `src/collect_face_data.py`

Purpose:

- CLI workflow for student registration and collecting face images via webcam.

Core logic:

- Takes student name and roll number as input.
- Generates structured `student_id`.
- Creates dataset folder for that student.
- Uses OpenCV camera and Haar cascade to detect face.
- Crops face ROI and saves `img1.jpg ... imgN.jpg`.
- Stores student record in database.

Notes:

- This module is interactive/CLI oriented.
- Current printed console text contains some legacy encoding artifacts from earlier edits; functional logic is unaffected.

Libraries used:

- `cv2` (OpenCV)
- `os`
- `time`
- `datetime`

## `src/encode_faces.py`

Purpose:

- Converts stored student images into face embeddings and saves them to a pickle file.

Core logic:

- Scans dataset folders.
- For each image:
  - loads image
  - detects face locations
  - creates encoding vector
- Stores encoding vectors and student IDs in:
  - `data/encodings/face_encodings.pkl`
- Output structure:
  - `{"encodings": [...], "names": [...]}`

Libraries used:

- `face_recognition`
- `pickle`
- `os`
- `pathlib`
- `cv2` (imported, but not central in encoding path)

## `src/entry_camera.py`

Purpose:

- Real-time entry-side recognition and entry logging.

Core logic:

- Loads known encodings from pickle.
- Captures webcam frames.
- Detects and encodes faces.
- Compares with known encodings using distance + tolerance.
- Marks entry in database if recognized and not already INSIDE.
- Uses cooldown and last-recognized tracking to reduce duplicate marks.

Libraries used:

- `cv2`
- `face_recognition`
- `pickle`
- `os`
- `datetime`
- `numpy`

## `src/exit_camera.py`

Purpose:

- Real-time exit-side recognition and attendance finalization.

Core logic:

- Uses `RecognitionService` for detection/recognition.
- On match, calls `process_exit`, which delegates to:
  - `DatabaseManager.mark_exit_and_save_attendance`
- Attendance record includes:
  - entry time
  - exit time
  - duration in minutes
  - status
  - subject (active subject from settings)
- Prevents back-to-back duplicate processing with short time window.

Libraries used:

- `time`
- `cv2`

## `src/recognition_service.py`

Purpose:

- Shared reusable recognition engine for both API and camera code.

Core logic:

- Loads and hot-reloads encodings when file timestamp changes.
- Accepts:
  - raw OpenCV frame
  - browser base64 image payload
- Performs optimized recognition:
  - optional frame downscale
  - face detection
  - encoding
  - distance match
  - confidence calculation
- Optional YOLO face detection path:
  - enabled only if model exists and ultralytics loads
  - falls back to `face_recognition.face_locations` otherwise

Libraries used:

- `base64`
- `os`
- `pickle`
- `typing`
- `cv2`
- `face_recognition`
- `numpy`
- `ultralytics` (optional runtime)

## `src/rate_limiter.py`

Purpose:

- Lightweight API rate limiter (in-memory, fixed window).

Core logic:

- Keeps per-key request timestamps in deques.
- Evicts timestamps outside the current time window.
- Returns:
  - allow/deny boolean
  - retry-after seconds when denied
- Thread-safe via `Lock`.

Libraries used:

- `collections`
- `threading`
- `time`
- `typing`

## `src/validators.py`

Purpose:

- Validation and normalization for API inputs.

Core logic:

- Defines `ValidationError` for clean API error responses.
- Validates:
  - student ID format
  - name
  - roll number (auto-cleans prefixes/separators)
  - subject values
  - status
  - camera run mode
  - dates
  - pagination params
  - base64 image size and integrity

Libraries used:

- `base64`
- `binascii`
- `re`
- `datetime`
- `typing`

## `src/utils.py`

Purpose:

- Report generation helpers and logger helper class.

Core logic:

- `ReportGenerator` creates:
  - CSV reports (all or date/subject filtered)
  - daily text reports
  - per-student text reports
- Pulls data through `DatabaseManager`.
- `Logger` class configures file + stream logging.
- `display_menu()` supports CLI mode.

Libraries used:

- `os`
- `csv`
- `logging`
- `datetime`
- `typing`

## 3. End-to-End Logic Flow

## Student registration and face data

1. Validate student fields.
2. Insert student into `students`.
3. Save multiple face images to `data/dataset/<student_id>/`.

## Encoding generation

1. Load all dataset images.
2. Generate face encodings.
3. Save compact encoding file (`face_encodings.pkl`).

## Entry recognition

1. Match face from camera/API image.
2. If recognized and not already INSIDE:
   - insert into `entry_log` with status `INSIDE`.

## Exit recognition and attendance

1. Match face again at exit.
2. Find latest INSIDE row for that student.
3. Update entry row status to EXITED.
4. Insert exit row into `exit_log`.
5. Compute duration and mark `PRESENT/ABSENT`.
6. Insert final row into `attendance` with selected subject.

## Reports and student view

1. Query attendance with subject/date filters.
2. Generate teacher-facing daily/CSV reports.
3. Student API endpoint returns subject-wise summary + detailed rows.

## 4. Libraries Used in Project (By Role)

Computer vision and recognition:

- `opencv-python` (`cv2`)
- `face_recognition`
- `numpy`
- `ultralytics` (optional YOLO face detection)

Web and API:

- `Flask`
- `waitress`
- `Pillow`

Data and storage:

- `sqlite3`
- `pickle`
- `csv`

Security and robustness:

- `logging` + `RotatingFileHandler`
- custom `RateLimiter`
- custom `validators`

Utility/standard library:

- `os`, `sys`, `time`, `uuid`, `base64`, `datetime`, `typing`, `re`, `threading`, `collections`

## 5. Key Design Decisions

1. SQLite for portability and easy demo/presentation setup.
2. Encodings in pickle for fast loading in local deployments.
3. Atomic exit + attendance write to prevent partial records.
4. Input validation centralized in `validators.py`.
5. Config centralized in `config.py` with environment override support.
6. Recognition logic centralized in `recognition_service.py` to avoid duplication between camera and web API flows.

## 6. Known Operational Notes

1. `attendance.db-wal` and `attendance.db-shm` are temporary SQLite runtime files; they are created when database is open and removed/compacted when processes close.
2. `__pycache__/` folders are generated Python bytecode caches and are not source files.
3. For stable demos, run one web server process at a time and ensure the camera is free (not in use by another app).
