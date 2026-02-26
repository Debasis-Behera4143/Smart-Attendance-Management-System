"""Flask web app for Smart Attendance Management System."""

import logging
import os
import sys
import time
import uuid
from datetime import datetime
from io import BytesIO
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, render_template, request, send_from_directory, g
from PIL import Image

# Add parent directory to path for src imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import src.config as config
from src.attendance_manager import AttendanceManager
from src.database_manager import DatabaseManager
from src.encode_faces import FaceEncoder
from src.rate_limiter import RateLimiter
from src.recognition_service import RecognitionService
from src.utils import ReportGenerator
from src.validators import (
    ValidationError,
    validate_camera_run_mode,
    parse_limit_offset,
    validate_base64_image,
    validate_date,
    validate_name,
    validate_roll_number,
    validate_subject,
    validate_status,
    validate_student_id,
)


def _configure_logging():
    os.makedirs(config.LOGS_PATH, exist_ok=True)
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    formatter = logging.Formatter(config.LOG_FORMAT)

    file_handler = RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


_configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_REQUEST_SIZE_MB * 1024 * 1024

db = DatabaseManager()
report_gen = ReportGenerator()
attendance_mgr = AttendanceManager()
recognizer = RecognitionService()
rate_limiter = RateLimiter(
    window_seconds=config.RATE_LIMIT_WINDOW_SECONDS,
    max_requests=config.RATE_LIMIT_MAX_REQUESTS,
)

PUBLIC_API_PATHS = {"/api/health"}


def _bool_from_any(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _int_from_any(value, default=0, minimum=1):
    if value in (None, ""):
        return max(minimum, int(default))
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return max(minimum, int(default))
    return max(minimum, parsed)


def _float_from_any(value, default=0.0, minimum=0.0):
    if value in (None, ""):
        return max(minimum, float(default))
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return max(minimum, float(default))
    return max(minimum, parsed)


def _json_error(message: str, status_code: int = 400):
    return jsonify({"success": False, "message": message, "request_id": g.get("request_id")}), status_code


def _json_body():
    return request.get_json(silent=True) or {}


def _safe_dataset_folder(student_id: str) -> str:
    root = os.path.abspath(config.DATASET_PATH)
    folder = os.path.abspath(os.path.join(root, student_id))
    if not folder.startswith(root + os.sep) and folder != root:
        raise ValidationError("invalid storage path")
    return folder


def _current_settings():
    settings = db.get_system_settings()
    camera_policy = settings.get("camera_policy", config.DEFAULT_CAMERA_POLICY)
    camera_run_mode = settings.get("camera_run_mode", config.DEFAULT_CAMERA_RUN_MODE)
    active_subject = settings.get("active_subject", config.DEFAULT_SUBJECT)
    run_interval_seconds = _int_from_any(
        settings.get("run_interval_seconds"), config.DEFAULT_RUN_INTERVAL_SECONDS, minimum=3
    )
    session_duration_minutes = _int_from_any(
        settings.get("session_duration_minutes"),
        config.DEFAULT_SESSION_DURATION_MINUTES,
        minimum=1,
    )
    fair_motion_threshold = _float_from_any(
        settings.get("fair_motion_threshold"),
        config.DEFAULT_FAIR_MOTION_THRESHOLD,
        minimum=0.0,
    )

    use_yolo_requested = _bool_from_any(
        settings.get("use_yolo"), config.ENABLE_YOLO_IF_AVAILABLE
    )
    yolo_active = recognizer.set_yolo_active(use_yolo_requested)
    return {
        "camera_policy": camera_policy,
        "camera_run_mode": camera_run_mode,
        "active_subject": active_subject,
        "run_interval_seconds": run_interval_seconds,
        "session_duration_minutes": session_duration_minutes,
        "fair_motion_threshold": fair_motion_threshold,
        "subject_options": config.SUBJECT_OPTIONS,
        "use_yolo": yolo_active,
        "use_yolo_requested": use_yolo_requested,
        "yolo_supported": recognizer.yolo_supported,
        "yolo_active": yolo_active,
        "recognition_interval_seconds": config.RECOGNITION_INTERVAL_SECONDS,
    }


def _dashboard_payload():
    today = datetime.now().strftime(config.REPORT_DATE_FORMAT)
    records = db.get_attendance_by_date(today)
    total = len(records)
    present = sum(1 for record in records if record[5] == "PRESENT")
    absent = sum(1 for record in records if record[5] == "ABSENT")
    return {
        "date": today,
        "total": total,
        "present": present,
        "absent": absent,
        "attendance_rate": round((present / total) * 100, 2) if total else 0,
        "records": records,
    }


def _student_payload():
    students = db.get_all_students()
    return [
        {
            "student_id": row[0],
            "name": row[1],
            "roll_number": row[2],
            "registered_date": row[3],
        }
        for row in students
    ]


def _attendance_payload(records):
    return [
        {
            "student_id": row[0],
            "name": row[1],
            "entry_time": row[2],
            "exit_time": row[3],
            "duration": row[4],
            "status": row[5],
            "date": row[6],
            "subject": row[7] if len(row) > 7 else config.DEFAULT_SUBJECT,
        }
        for row in records
    ]


def _recent_entries_payload(limit=config.MAX_RECENT_ITEMS):
    rows = db.get_recent_entries(limit=limit)
    return [
        {
            "student_id": row[0],
            "name": row[1],
            "entry_time": row[2],
            "status": row[3],
        }
        for row in rows
    ]


def _recent_exits_payload(limit=config.MAX_RECENT_ITEMS):
    rows = db.get_recent_exits(limit=limit)
    return [
        {
            "student_id": row[0],
            "name": row[1],
            "entry_time": row[2],
            "exit_time": row[3],
            "duration": row[4],
            "status": row[5],
            "date": row[6],
            "subject": row[7] if len(row) > 7 else config.DEFAULT_SUBJECT,
        }
        for row in rows
    ]


def _inside_payload(limit=config.MAX_RECENT_ITEMS):
    rows = db.get_inside_students(limit=limit)
    return [
        {
            "student_id": row[0],
            "name": row[1],
            "entry_time": row[2],
            "date": row[3],
        }
        for row in rows
    ]


def _recognize_or_error(image_data):
    if not image_data:
        return None, _json_error("image payload is required", 400)

    validate_base64_image(image_data)
    match = recognizer.recognize_from_base64(image_data)
    if not match:
        return None, _json_error("face not recognized", 404)

    return match, None


@app.before_request
def _before_request():
    g.started_at = time.perf_counter()
    g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    if not request.path.startswith("/api/"):
        return None

    if config.REQUIRE_API_KEY and request.path not in PUBLIC_API_PATHS:
        provided = request.headers.get(config.API_KEY_HEADER, "").strip()
        if not provided or provided != config.API_KEY:
            return _json_error("unauthorized", 401)

    key = f"{request.remote_addr}:{request.path}"
    allowed, retry_after = rate_limiter.check(key)
    if not allowed:
        response, status = _json_error("rate limit exceeded", 429)
        response.headers["Retry-After"] = str(retry_after)
        return response, status

    return None


@app.after_request
def _after_request(response):
    response.headers["X-Request-ID"] = g.get("request_id", "")
    if request.path.startswith("/api/"):
        elapsed_ms = int((time.perf_counter() - g.get("started_at", time.perf_counter())) * 1000)
        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%s",
            g.get("request_id"),
            request.method,
            request.path,
            response.status_code,
            elapsed_ms,
        )
    return response


@app.errorhandler(ValidationError)
def _handle_validation_error(exc):
    return _json_error(str(exc), 400)


@app.errorhandler(413)
def _handle_payload_too_large(_exc):
    return _json_error("request payload too large", 413)


@app.errorhandler(Exception)
def _handle_unexpected_error(exc):
    logger.exception("Unhandled exception")
    if request.path.startswith("/api/"):
        return _json_error("internal server error", 500)
    raise exc


@app.route("/")
@app.route("/dashboard")
def dashboard():
    payload = _dashboard_payload()
    return render_template(
        "dashboard.html",
        stats={
            "date": payload["date"],
            "total": payload["total"],
            "present": payload["present"],
            "absent": payload["absent"],
            "attendance_rate": payload["attendance_rate"],
        },
        records=payload["records"],
    )


@app.route("/register")
def register_page():
    return render_template(
        "register.html",
        images_per_student=config.IMAGES_PER_STUDENT,
    )


@app.route("/entry")
def entry_page():
    settings = _current_settings()
    return render_template("entry.html", settings=settings)


@app.route("/exit")
def exit_page():
    settings = _current_settings()
    return render_template(
        "exit.html",
        settings=settings,
        min_duration=config.MINIMUM_DURATION,
    )


@app.route("/reports")
def reports_page():
    selected_subject = validate_subject(
        request.args.get("subject"), "subject", allow_empty=True
    )
    all_records = db.get_all_attendance(subject=selected_subject)
    students = db.get_all_students()
    today = datetime.now().strftime(config.REPORT_DATE_FORMAT)
    return render_template(
        "reports.html",
        records=all_records,
        students=students,
        today=today,
        subjects=config.SUBJECT_OPTIONS,
        selected_subject=selected_subject,
    )


@app.route("/student-attendance")
def student_attendance_page():
    return render_template(
        "student_attendance.html",
        subjects=config.SUBJECT_OPTIONS,
    )


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "GET":
        settings = _current_settings()
        return jsonify({"success": True, "settings": settings, "runtime": recognizer.get_runtime_info()})

    data = _json_body()
    camera_policy = data.get("camera_policy")
    if camera_policy is not None:
        if camera_policy not in {
            config.CAMERA_POLICY_ALWAYS_ON,
            config.CAMERA_POLICY_ON_DEMAND,
        }:
            raise ValidationError("invalid camera policy")
        db.set_setting("camera_policy", camera_policy)

    if "camera_run_mode" in data:
        run_mode = validate_camera_run_mode(data.get("camera_run_mode"))
        db.set_setting("camera_run_mode", run_mode)

    if "active_subject" in data:
        active_subject = validate_subject(data.get("active_subject"))
        db.set_setting("active_subject", active_subject)

    if "run_interval_seconds" in data:
        interval_seconds = _int_from_any(data.get("run_interval_seconds"), minimum=3)
        db.set_setting("run_interval_seconds", str(interval_seconds))

    if "session_duration_minutes" in data:
        session_minutes = _int_from_any(data.get("session_duration_minutes"), minimum=1)
        db.set_setting("session_duration_minutes", str(session_minutes))

    if "fair_motion_threshold" in data:
        motion_threshold = _float_from_any(data.get("fair_motion_threshold"), minimum=0.0)
        db.set_setting("fair_motion_threshold", str(motion_threshold))

    if "use_yolo" in data:
        use_yolo = _bool_from_any(data.get("use_yolo"))
        db.set_setting("use_yolo", str(use_yolo).lower())

    settings = _current_settings()
    return jsonify({"success": True, "settings": settings, "runtime": recognizer.get_runtime_info()})


@app.route("/api/health")
def api_health():
    return jsonify(
        {
            "success": True,
            "timestamp": datetime.now().strftime(config.REPORT_DATETIME_FORMAT),
            "runtime": recognizer.get_runtime_info(),
            "settings": _current_settings(),
        }
    )


@app.route("/api/register-student", methods=["POST"])
def register_student():
    data = _json_body()
    student_id = validate_student_id(data.get("student_id"))
    name = validate_name(data.get("name"))
    roll_number = validate_roll_number(data.get("roll_number"))

    success = db.register_student(student_id, name, roll_number)
    if success:
        return jsonify({"success": True, "message": "Student registered successfully"})
    return _json_error("student_id or roll_number already exists", 409)


@app.route("/api/save-face-images", methods=["POST"])
def save_face_images():
    data = _json_body()
    student_id = validate_student_id(data.get("student_id"))
    images = data.get("images") or []

    if not isinstance(images, list) or not images:
        raise ValidationError("at least one image is required")
    if len(images) > config.MAX_IMAGES_PER_UPLOAD:
        raise ValidationError(
            f"too many images in one request (max {config.MAX_IMAGES_PER_UPLOAD})"
        )

    folder_path = _safe_dataset_folder(student_id)
    os.makedirs(folder_path, exist_ok=True)

    saved_count = 0
    for index, image_payload in enumerate(images, start=1):
        try:
            image_bytes = validate_base64_image(image_payload)
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            image.save(os.path.join(folder_path, f"img{index}.jpg"), "JPEG", quality=90)
            saved_count += 1
        except ValidationError:
            continue
        except Exception:
            logger.warning("invalid image skipped at index=%s for student_id=%s", index, student_id)

    if saved_count == 0:
        raise ValidationError("no valid images were saved")

    return jsonify({"success": True, "message": f"saved {saved_count} images"})


@app.route("/api/generate-encodings", methods=["POST"])
def generate_encodings():
    encoder = FaceEncoder()
    success = encoder.run()
    if success:
        recognizer.load_encodings(force=True)
        return jsonify({"success": True, "message": "encodings generated successfully"})
    return _json_error("failed to generate encodings", 500)


@app.route("/api/recognize-entry", methods=["POST"])
def recognize_entry():
    data = _json_body()
    image_data = data.get("image")
    match, error_response = _recognize_or_error(image_data)
    if error_response:
        return error_response

    student_id = match["student_id"]
    name = validate_name(match["name"])
    confidence = match["confidence"]

    if not db.get_student_info(student_id):
        return _json_error("recognized student is not registered", 404)

    entry_id = db.mark_entry(student_id, name)
    if not entry_id:
        return _json_error(f"{name} is already marked inside", 409)

    entry_time = datetime.now().strftime(config.REPORT_DATETIME_FORMAT)
    return jsonify(
        {
            "success": True,
            "message": "entry marked successfully",
            "entry_id": entry_id,
            "student_id": student_id,
            "student_name": name,
            "confidence": confidence,
            "entry_time": entry_time,
        }
    )


@app.route("/api/recognize-exit", methods=["POST"])
def recognize_exit():
    data = _json_body()
    image_data = data.get("image")
    subject = validate_subject(data.get("subject"), "subject", allow_empty=True)
    if not subject:
        subject = db.get_setting("active_subject", config.DEFAULT_SUBJECT)
    match, error_response = _recognize_or_error(image_data)
    if error_response:
        return error_response

    student_id = match["student_id"]
    name = validate_name(match["name"])
    confidence = match["confidence"]

    if not db.get_student_info(student_id):
        return _json_error("recognized student is not registered", 404)

    exit_result = db.mark_exit_and_save_attendance(
        student_id=student_id,
        name=name,
        minimum_duration=attendance_mgr.minimum_duration,
        subject=subject,
    )
    if not exit_result:
        return _json_error(f"no active entry found for {name}", 409)

    return jsonify(
        {
            "success": True,
            "message": "exit marked and attendance recorded",
            "student_id": student_id,
            "student_name": name,
            "confidence": confidence,
            "entry_time": exit_result["entry_time"],
            "exit_time": exit_result["exit_time"],
            "duration_minutes": exit_result["duration"],
            "attendance_status": exit_result["status"],
            "date": exit_result["date"],
            "subject": exit_result["subject"],
        }
    )


# Backward compatible aliases
@app.route("/api/mark-entry", methods=["POST"])
def mark_entry():
    data = _json_body()
    if data.get("image"):
        return recognize_entry()

    student_id = validate_student_id(data.get("student_id"))
    name = validate_name(data.get("name"))

    if not db.get_student_info(student_id):
        return _json_error("student not registered", 404)

    entry_id = db.mark_entry(student_id, name)
    if not entry_id:
        return _json_error(f"{name} is already marked inside", 409)

    return jsonify(
        {
            "success": True,
            "message": "entry marked successfully",
            "entry_id": entry_id,
            "student_id": student_id,
            "student_name": name,
            "entry_time": datetime.now().strftime(config.REPORT_DATETIME_FORMAT),
        }
    )


@app.route("/api/mark-exit", methods=["POST"])
def mark_exit():
    data = _json_body()
    if data.get("image"):
        return recognize_exit()

    student_id = validate_student_id(data.get("student_id"))
    name = validate_name(data.get("name"))
    subject = validate_subject(data.get("subject"), "subject", allow_empty=True)
    if not subject:
        subject = db.get_setting("active_subject", config.DEFAULT_SUBJECT)

    if not db.get_student_info(student_id):
        return _json_error("student not registered", 404)

    exit_result = db.mark_exit_and_save_attendance(
        student_id=student_id,
        name=name,
        minimum_duration=attendance_mgr.minimum_duration,
        subject=subject,
    )
    if not exit_result:
        return _json_error("no active entry found", 409)

    return jsonify(
        {
            "success": True,
            "message": "exit marked successfully",
            "student_id": student_id,
            "student_name": name,
            "entry_time": exit_result["entry_time"],
            "exit_time": exit_result["exit_time"],
            "duration_minutes": exit_result["duration"],
            "attendance_status": exit_result["status"],
            "date": exit_result["date"],
            "subject": exit_result["subject"],
        }
    )


@app.route("/api/manual-attendance", methods=["POST"])
def manual_attendance():
    """Manual correction endpoint for teachers/admins."""
    data = _json_body()
    student_id = validate_student_id(data.get("student_id"))
    name = validate_name(data.get("name"))
    entry_time = (data.get("entry_time") or "").strip()
    exit_time = (data.get("exit_time") or "").strip()
    status_override = data.get("status")
    subject = validate_subject(data.get("subject"), "subject", allow_empty=True)
    if not subject:
        subject = db.get_setting("active_subject", config.DEFAULT_SUBJECT)

    if not db.get_student_info(student_id):
        return _json_error("student not registered", 404)

    try:
        entry_dt = datetime.strptime(entry_time, config.REPORT_DATETIME_FORMAT)
        exit_dt = datetime.strptime(exit_time, config.REPORT_DATETIME_FORMAT)
    except ValueError as exc:
        raise ValidationError(
            f"entry_time and exit_time must match {config.REPORT_DATETIME_FORMAT}"
        ) from exc

    if exit_dt < entry_dt:
        raise ValidationError("exit_time cannot be earlier than entry_time")

    duration = int((exit_dt - entry_dt).total_seconds() / 60)
    status = validate_status(status_override) if status_override else attendance_mgr.determine_status(duration)
    date = entry_dt.strftime(config.REPORT_DATE_FORMAT)

    saved = db.upsert_attendance(
        student_id=student_id,
        name=name,
        entry_time=entry_time,
        exit_time=exit_time,
        duration=duration,
        status=status,
        date=date,
        subject=subject,
    )
    if not saved:
        return _json_error("failed to save manual attendance", 500)

    return jsonify(
        {
            "success": True,
            "message": "manual attendance saved",
            "student_id": student_id,
            "student_name": name,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "duration_minutes": duration,
            "attendance_status": status,
            "date": date,
            "subject": subject,
        }
    )


@app.route("/api/recent-entries")
def recent_entries():
    return jsonify({"success": True, "entries": _recent_entries_payload()})


@app.route("/api/recent-exits")
def recent_exits():
    return jsonify({"success": True, "exits": _recent_exits_payload()})


@app.route("/api/inside-students")
def inside_students():
    limit, _ = parse_limit_offset(request.args.get("limit"), 0)
    return jsonify({"success": True, "inside": _inside_payload(limit=limit)})


@app.route("/api/analytics")
def analytics():
    from_date = validate_date(request.args.get("from_date"), "from_date")
    to_date = validate_date(request.args.get("to_date"), "to_date")
    return jsonify({"success": True, "analytics": db.get_analytics(from_date, to_date)})


@app.route("/api/get-students")
def get_students():
    return jsonify({"success": True, "students": _student_payload()})


@app.route("/api/get-today-attendance")
def get_today_attendance():
    today = datetime.now().strftime(config.REPORT_DATE_FORMAT)
    records = db.get_attendance_by_date(today)
    return jsonify({"success": True, "attendance": _attendance_payload(records)})


@app.route("/api/get-attendance")
def get_attendance():
    date = validate_date(request.args.get("date"), "date")
    student_id = request.args.get("student_id")
    if student_id:
        student_id = validate_student_id(student_id)

    status = request.args.get("status")
    if status:
        status = validate_status(status)

    subject = validate_subject(request.args.get("subject"), "subject", allow_empty=True)

    limit, offset = parse_limit_offset(request.args.get("limit"), request.args.get("offset"))
    records, total = db.get_attendance_filtered(
        date=date,
        student_id=student_id,
        status=status,
        subject=subject,
        limit=limit,
        offset=offset,
    )

    return jsonify(
        {
            "success": True,
            "records": _attendance_payload(records),
            "total": total,
            "limit": limit,
            "offset": offset,
            "subject": subject,
        }
    )


@app.route("/api/student-attendance")
def api_student_attendance():
    student_id = validate_student_id(request.args.get("student_id"))
    subject = validate_subject(request.args.get("subject"), "subject", allow_empty=True)
    limit, _ = parse_limit_offset(request.args.get("limit"), 0)

    student = db.get_student_info(student_id)
    if not student:
        return _json_error("student not registered", 404)

    records = db.get_student_subject_records(
        student_id=student_id,
        subject=subject,
        limit=limit,
    )
    summary = db.get_student_subject_summary(student_id)

    return jsonify(
        {
            "success": True,
            "student": {
                "student_id": student[0],
                "name": student[1],
                "roll_number": student[2],
                "registered_date": student[3],
            },
            "subject": subject,
            "subject_summary": summary,
            "records": _attendance_payload(records),
        }
    )


@app.route("/api/generate-report", methods=["POST"])
def api_generate_report():
    data = _json_body()
    report_type = (data.get("type") or "daily").strip().lower()
    date = validate_date(data.get("date"), "date")
    subject = validate_subject(data.get("subject"), "subject", allow_empty=True)

    if report_type == "daily":
        report_path = report_gen.generate_daily_report(date, subject=subject)
    elif report_type == "csv":
        report_path = report_gen.generate_csv_report(date, subject=subject)
    else:
        raise ValidationError("type must be 'daily' or 'csv'")

    file_name = os.path.basename(report_path)
    return jsonify(
        {
            "success": True,
            "message": "report generated successfully",
            "path": report_path,
            "file_name": file_name,
            "subject": subject,
        }
    )


@app.route("/api/download-report")
def download_report():
    file_name = (request.args.get("file") or "").strip()
    if not file_name:
        raise ValidationError("missing file parameter")

    safe_name = os.path.basename(file_name)
    full_path = os.path.join(config.REPORTS_PATH, safe_name)
    if not os.path.exists(full_path):
        return _json_error("report file not found", 404)

    return send_from_directory(config.REPORTS_PATH, safe_name, as_attachment=True)


if __name__ == "__main__":
    os.makedirs(config.DATASET_PATH, exist_ok=True)
    os.makedirs(config.ENCODINGS_PATH, exist_ok=True)
    os.makedirs(config.DATABASE_PATH, exist_ok=True)
    os.makedirs(config.LOGS_PATH, exist_ok=True)
    os.makedirs(config.REPORTS_PATH, exist_ok=True)

    app.run(debug=config.FLASK_DEBUG, host=config.FLASK_HOST, port=config.FLASK_PORT)
