# CCTV Setup Guide

This guide covers how to configure and run CCTV-based attendance using `run_cctv_system.py`.

## 1. Prerequisites

- Python virtual environment created in project root (`.venv`)
- Dependencies installed from `requirements.txt`
- At least one registered student with generated face encodings
- A valid camera source:
  - USB camera index (`0`, `1`, ...)
  - RTSP URL (`rtsp://user:pass@ip:port/path`)
  - HTTP/MJPEG URL (`http://ip:port/video`)

## 2. One-Time Project Setup

From project root:

```powershell
cd "c:\Users\debas\OneDrive\Desktop\Smart-Attendance-System"
python -m venv .venv
.\.venv\Scripts\activate
pip install cmake
pip install -r requirements.txt
New-Item -Path "data/database","data/dataset","data/encodings","data/logs","data/reports" -ItemType Directory -Force
python -c "from src.database_manager import DatabaseManager; DatabaseManager()"
```

## 3. Add Students First (Required)

CCTV recognition needs `data/encodings/face_encodings.pkl`.

Use either:

1. Web registration flow (`http://127.0.0.1:5000` -> Register page), or
2. CLI collection:

```powershell
python -m src.collect_face_data
```

If you manually added/changed dataset images, regenerate encodings:

```powershell
python -m src.encode_faces
```

## 4. Configure CCTV Streams

Set environment variables in the same terminal session before running CCTV:

```powershell
$env:SMART_ATTENDANCE_ENTRY_CAMERA_STREAM="rtsp://user:pass@192.168.1.10:554/stream1"
$env:SMART_ATTENDANCE_EXIT_CAMERA_STREAM="rtsp://user:pass@192.168.1.11:554/stream1"
```

Notes:

- If `SMART_ATTENDANCE_EXIT_CAMERA_STREAM` is empty, run only entry mode.
- `SMART_ATTENDANCE_CCTV_STREAM_URL` is a fallback for entry when entry stream is not set.
- Numeric values like `"0"` are treated as local USB camera IDs.

## 5. Run CCTV Processor

Both streams:

```powershell
python run_cctv_system.py --mode both
```

Entry only:

```powershell
python run_cctv_system.py --mode entry
```

Exit only:

```powershell
python run_cctv_system.py --mode exit
```

Headless mode (no OpenCV window):

```powershell
python run_cctv_system.py --mode both --no-display
```

Optional subject override:

```powershell
python run_cctv_system.py --mode entry --subject "Machine Learning"
```

## 6. Useful Runtime Settings

You can tune behavior with these environment variables:

- `SMART_ATTENDANCE_FRAME_PROCESS_INTERVAL` (default: `5`)
- `SMART_ATTENDANCE_RECOGNITION_CONFIDENCE_THRESHOLD` (default: `70.0`)
- `SMART_ATTENDANCE_DUPLICATE_ATTENDANCE_WINDOW_SECONDS` (default: `300`)
- `SMART_ATTENDANCE_CAMERA_RECONNECT_ATTEMPTS` (default: `3`)
- `SMART_ATTENDANCE_CAMERA_RECONNECT_DELAY` (default: `5`)
- `SMART_ATTENDANCE_CAMERA_BUFFER_SIZE` (default: `1`)
- `SMART_ATTENDANCE_CCTV_SHOW_LIVE_DISPLAY` (default: `true`)
- `SMART_ATTENDANCE_CCTV_DISPLAY_WIDTH` (default: `640`)

Example:

```powershell
$env:SMART_ATTENDANCE_FRAME_PROCESS_INTERVAL="3"
$env:SMART_ATTENDANCE_RECOGNITION_CONFIDENCE_THRESHOLD="75"
python run_cctv_system.py --mode both
```

## 7. Logs and Verification

- CCTV logs: `data/logs/cctv_system_logs.txt`
- App logs: `data/logs/system_logs.txt`

Expected startup output includes:

- Mode and stream values
- Frame interval and confidence threshold
- "Press Ctrl+C to stop all processors."

Stop with `Ctrl+C`.

## 8. Troubleshooting

No CCTV streams configured

- Set `SMART_ATTENDANCE_ENTRY_CAMERA_STREAM` or pass `--entry-stream`.
- For exit mode, set `SMART_ATTENDANCE_EXIT_CAMERA_STREAM` or pass `--exit-stream`.

No encodings available

- Run `python -m src.encode_faces`.
- Verify `data/encodings/face_encodings.pkl` exists.

Camera open failed

- Confirm stream URL works in VLC/OpenCV.
- Check camera credentials/IP/port/path.
- Try increasing reconnect delay:

```powershell
$env:SMART_ATTENDANCE_CAMERA_RECONNECT_DELAY="8"
```

Waiting for frames

- Stream is reachable but no frames are being decoded.
- Lower latency by keeping `SMART_ATTENDANCE_CAMERA_BUFFER_SIZE=1`.

Low recognition quality

- Add clearer face images per student.
- Improve camera angle and lighting.
- Increase strictness by raising confidence threshold.
