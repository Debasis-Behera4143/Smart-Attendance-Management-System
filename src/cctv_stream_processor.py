"""CCTV stream processing for automated attendance marking."""



from __future__ import annotations



import logging

import os

import threading

import time

from dataclasses import dataclass

from datetime import datetime

from logging.handlers import RotatingFileHandler

from typing import Dict, List, Optional, Tuple



import cv2

import face_recognition

import numpy as np



from . import config

from .database_manager import DatabaseManager

from .recognition_service import RecognitionService

from .threaded_camera_capture import ThreadedCameraCapture





FaceLocation = Tuple[int, int, int, int]





@dataclass

class FaceDetectionResult:

    """Structured result for one detected face in a frame."""



    bbox: FaceLocation

    name: str

    student_id: Optional[str]

    confidence: float

    is_recognized: bool

    status: str = ""





def _configure_cctv_logger() -> logging.Logger:

    """Create a dedicated CCTV logger that writes to data/logs/cctv_system_logs.txt."""

    logger = logging.getLogger("cctv_system")

    if logger.handlers:

        return logger



    os.makedirs(config.LOGS_PATH, exist_ok=True)

    log_file = os.path.join(config.LOGS_PATH, "cctv_system_logs.txt")

    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

    formatter = logging.Formatter(config.LOG_FORMAT)



    file_handler = RotatingFileHandler(

        log_file,

        maxBytes=config.LOG_MAX_BYTES,

        backupCount=config.LOG_BACKUP_COUNT,

        encoding="utf-8",

    )

    file_handler.setFormatter(formatter)



    stream_handler = logging.StreamHandler()

    stream_handler.setFormatter(formatter)



    logger.setLevel(level)

    logger.addHandler(file_handler)

    logger.addHandler(stream_handler)

    logger.propagate = False

    return logger





class CCTVStreamProcessor:

    """Processes one CCTV stream for entry or exit attendance."""



    def __init__(

        self,

        stream_url: str,

        camera_role: str = "entry",

        camera_name: Optional[str] = None,

        subject: Optional[str] = None,

        show_live_display: Optional[bool] = None,

    ):

        role = (camera_role or "").strip().lower()

        if role not in {"entry", "exit"}:

            raise ValueError("camera_role must be 'entry' or 'exit'")



        self.stream_url = (stream_url or "").strip()

        self.camera_role = role

        self.camera_name = camera_name or f"{role.title()} Camera"

        self.subject_override = (subject or "").strip() or None

        self.show_live_display = (

            config.CCTV_SHOW_LIVE_DISPLAY if show_live_display is None else bool(show_live_display)

        )

        self.window_name = f"CCTV - {self.camera_name} ({self.camera_role.upper()})"



        self.logger = _configure_cctv_logger()

        self.db = DatabaseManager()

        self.recognizer = RecognitionService()

        self.capture = ThreadedCameraCapture(self.stream_url, self.camera_name, self.logger)



        self.frame_process_interval = max(1, config.FRAME_PROCESS_INTERVAL)

        self.confidence_threshold = float(config.RECOGNITION_CONFIDENCE_THRESHOLD)

        self.duplicate_window_seconds = max(1, config.DUPLICATE_ATTENDANCE_WINDOW_SECONDS)

        self.display_width = max(320, config.CCTV_DISPLAY_WIDTH)

        self.loop_sleep_seconds = max(0.0, config.CCTV_LOOP_SLEEP_SECONDS)



        self._frame_index = 0

        self._last_detections: List[FaceDetectionResult] = []

        self._stop_event = threading.Event()

        self._recent_marks: Dict[Tuple[str, str, str], datetime] = {}

        self._last_missing_encodings_log_at = 0.0

        self._last_frame_warning_ts = 0.0

        self._settings_cache: Dict[str, Tuple[float, object]] = {}

        self._settings_cache_ttl_seconds = 1.0



    def run_in_thread(self, stop_event: Optional[threading.Event] = None) -> threading.Thread:

        """Start processor in a background thread."""

        thread = threading.Thread(

            target=self.run,

            kwargs={"stop_event": stop_event},

            name=f"processor-{self.camera_name}",

            daemon=True,

        )

        thread.start()

        return thread



    def stop(self):

        self._stop_event.set()



    def run(self, stop_event: Optional[threading.Event] = None):

        """Main loop: capture frame, recognize face, mark attendance, display result."""

        if not self.stream_url:

            self.logger.error(

                "Empty stream URL for %s processor. Configure entry/exit camera streams first.",

                self.camera_role,

            )

            return



        self.capture.start()

        self.logger.info(

            "CCTV processor started | role=%s | camera=%s | interval=%s | threshold=%.2f",

            self.camera_role,

            self.camera_name,

            self.frame_process_interval,

            self.confidence_threshold,

        )



        try:

            while not self._stop_event.is_set() and not (stop_event and stop_event.is_set()):

                ok, frame = self.capture.get_latest_frame(copy=False)

                if not ok or frame is None:

                    now = time.time()

                    if now - self._last_frame_warning_ts >= 5.0:

                        self.logger.warning(

                            "Waiting for frames from camera | role=%s | camera=%s",

                            self.camera_role,

                            self.camera_name,

                        )

                        self._last_frame_warning_ts = now

                    time.sleep(0.1)

                    continue



                frame = self._resize_frame(frame)

                self._frame_index += 1



                if self._frame_index % self.frame_process_interval == 0:

                    self._last_detections = self._process_frame(frame)



                if self.show_live_display:

                    annotated = frame.copy()

                    self._draw_detections(annotated, self._last_detections)

                    try:

                        cv2.imshow(self.window_name, annotated)

                        key = cv2.waitKey(1) & 0xFF

                        if key == ord("q"):

                            self.logger.info(

                                "Quit requested from display window | role=%s | camera=%s",

                                self.camera_role,

                                self.camera_name,

                            )

                            if stop_event is not None:

                                stop_event.set()

                            self._stop_event.set()

                            break

                    except cv2.error:



                        self.show_live_display = False

                        self.logger.warning(

                            "OpenCV display unavailable; continuing in headless mode | camera=%s",

                            self.camera_name,

                        )



                if self.loop_sleep_seconds > 0:

                    time.sleep(self.loop_sleep_seconds)

        finally:

            self.capture.stop()

            if self.show_live_display:

                try:

                    cv2.destroyWindow(self.window_name)

                except cv2.error:

                    pass

            self.logger.info("CCTV processor stopped | role=%s | camera=%s", self.camera_role, self.camera_name)



    def _resize_frame(self, frame: np.ndarray) -> np.ndarray:

        height, width = frame.shape[:2]

        if width <= self.display_width:

            return frame

        ratio = self.display_width / float(width)

        resized_height = max(1, int(height * ratio))

        return cv2.resize(frame, (self.display_width, resized_height))



    def _process_frame(self, frame: np.ndarray) -> List[FaceDetectionResult]:

        if not self.recognizer.load_encodings():

            now = time.time()

            if now - self._last_missing_encodings_log_at >= 10.0:

                self.logger.warning(

                    "No encodings available; run face encoding generation first."

                )

                self._last_missing_encodings_log_at = now

            return []



        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        face_locations = self._detect_faces(rgb_frame)

        if not face_locations:

            return []



        try:

            face_encodings = face_recognition.face_encodings(

                rgb_frame,

                face_locations,

                model=config.FACE_ENCODING_MODEL,

            )

        except Exception:

            self.logger.exception("Failed generating face encodings from frame.")

            return []



        results: List[FaceDetectionResult] = []

        for location, face_encoding in zip(face_locations, face_encodings):

            match = self._match_face(location, face_encoding)

            if match.is_recognized:

                match.status = self._mark_attendance(match)

            else:

                match.status = "Unknown"

            results.append(match)



        return results



    def _detect_faces(self, rgb_frame: np.ndarray) -> List[FaceLocation]:

        try:

            locations = face_recognition.face_locations(

                rgb_frame, model=config.FACE_DETECTION_MODEL

            )

            if locations:

                return locations

        except Exception:

            self.logger.exception("Face detection failed using %s model.", config.FACE_DETECTION_MODEL)



        if self.recognizer.yolo_active:

            try:

                return self.recognizer._detect_faces_with_yolo(rgb_frame)

            except Exception:

                self.logger.exception("YOLO face detection fallback failed.")



        return []



    @staticmethod

    def _unknown_match(location: FaceLocation, confidence: float = 0.0) -> FaceDetectionResult:

        return FaceDetectionResult(

            bbox=location,

            name="Unknown",

            student_id=None,

            confidence=confidence,

            is_recognized=False,

        )



    def _match_face(self, location: FaceLocation, face_encoding: np.ndarray) -> FaceDetectionResult:

        if not self.recognizer.known_encodings:

            return self._unknown_match(location)



        face_distances = face_recognition.face_distance(

            self.recognizer.known_encodings,

            face_encoding,

        )

        if len(face_distances) == 0:

            return self._unknown_match(location)



        best_index = int(np.argmin(face_distances))

        best_distance = float(face_distances[best_index])

        confidence = max(0.0, min(100.0, (1.0 - best_distance) * 100.0))



        within_tolerance = best_distance <= config.FACE_RECOGNITION_TOLERANCE

        above_threshold = confidence >= self.confidence_threshold

        if not (within_tolerance and above_threshold):

            return self._unknown_match(location, confidence=round(confidence, 2))



        student_id = self.recognizer.known_names[best_index]

        name = self.recognizer._extract_name(student_id)

        return FaceDetectionResult(

            bbox=location,

            name=name,

            student_id=student_id,

            confidence=round(confidence, 2),

            is_recognized=True,

        )



    def _mark_attendance(self, match: FaceDetectionResult) -> str:

        if not match.student_id:

            return "Unknown"



        active_subject = self._get_active_subject()

        now_dt = datetime.now()

        student_id = match.student_id

        name = match.name



        if self._is_duplicate_recent(student_id, active_subject, now_dt):

            return self._remember_and_status(student_id, active_subject, now_dt, "Duplicate blocked")



        student = self.db.get_student_info(student_id)

        if not student:

            self.logger.warning(

                "Recognized face not present in students table | student_id=%s",

                student_id,

            )

            return "Not registered"



        roll_number = student[2]



        if self.camera_role == "entry":

            entry_result = self.db.mark_entry(student_id, name, subject=active_subject)

            if not entry_result:

                return self._remember_and_status(student_id, active_subject, now_dt, "Already inside")



            mark_time = str(entry_result["entry_time"])

            self._remember_mark(student_id, active_subject, now_dt)

            self._log_attendance_event(

                event_type="ENTRY",

                name=name,

                roll_number=roll_number,

                student_id=student_id,

                subject=active_subject,

                mark_time=mark_time,

                confidence=match.confidence,

            )

            return "Entry marked"



        minimum_duration = self._get_minimum_duration()

        exit_result = self.db.mark_exit_and_save_attendance(

            student_id=student_id,

            name=name,

            minimum_duration=minimum_duration,

            subject=active_subject,

        )

        if not exit_result:

            return self._remember_and_status(student_id, active_subject, now_dt, "No active entry")



        resolved_subject = str(exit_result.get("subject", active_subject))

        mark_time = str(exit_result.get("exit_time", now_dt.strftime(config.REPORT_DATETIME_FORMAT)))

        attendance_status = str(exit_result.get("status", "UNKNOWN"))



        self._remember_mark(student_id, resolved_subject, now_dt)

        self._log_attendance_event(

            event_type=f"EXIT_{attendance_status}",

            name=name,

            roll_number=roll_number,

            student_id=student_id,

            subject=resolved_subject,

            mark_time=mark_time,

            confidence=match.confidence,

        )

        return f"Exit marked ({attendance_status})"



    def _remember_and_status(

        self,

        student_id: str,

        subject: str,

        timestamp: datetime,

        status: str,

    ) -> str:

        self._remember_mark(student_id, subject, timestamp)

        return status



    def _get_active_subject(self) -> str:

        if self.subject_override:

            return self.subject_override

        return str(

            self._get_cached_setting("active_subject", config.DEFAULT_SUBJECT)

            or config.DEFAULT_SUBJECT

        )



    def _get_minimum_duration(self) -> int:

        raw_value = self._get_cached_setting(

            "minimum_duration_minutes",

            str(config.MINIMUM_DURATION),

            ttl_seconds=3.0,

        )

        try:

            return max(1, int(raw_value or config.MINIMUM_DURATION))

        except (TypeError, ValueError):

            return config.MINIMUM_DURATION



    def _get_cached_setting(

        self,

        key: str,

        default: object,

        ttl_seconds: Optional[float] = None,

    ) -> object:

        ttl = self._settings_cache_ttl_seconds if ttl_seconds is None else max(0.0, ttl_seconds)

        now = time.monotonic()

        cached = self._settings_cache.get(key)

        if cached and (now - cached[0]) < ttl:

            return cached[1]



        try:

            value = self.db.get_setting(key, default)

        except Exception:

            self.logger.exception("Failed reading setting | key=%s", key)

            value = default



        self._settings_cache[key] = (now, value)

        return value



    def _cache_key(self, student_id: str, subject: str) -> Tuple[str, str, str]:

        return self.camera_role, student_id, subject



    def _remember_mark(self, student_id: str, subject: str, timestamp: datetime):

        self._recent_marks[self._cache_key(student_id, subject)] = timestamp

        cutoff = timestamp.timestamp() - float(self.duplicate_window_seconds)

        stale_keys = [

            key

            for key, value in self._recent_marks.items()

            if value.timestamp() < cutoff

        ]

        for key in stale_keys:

            self._recent_marks.pop(key, None)



    def _is_duplicate_recent(self, student_id: str, subject: str, now_dt: datetime) -> bool:

        key = self._cache_key(student_id, subject)

        cached_at = self._recent_marks.get(key)

        if cached_at and (now_dt - cached_at).total_seconds() < self.duplicate_window_seconds:

            return True



        last_db_mark = self._get_last_db_mark_time(student_id, subject)

        if last_db_mark and (now_dt - last_db_mark).total_seconds() < self.duplicate_window_seconds:

            self._recent_marks[key] = last_db_mark

            return True



        return False



    def _get_last_db_mark_time(self, student_id: str, subject: str) -> Optional[datetime]:

        column, table = ("entry_time", "entry_log") if self.camera_role == "entry" else ("exit_time", "attendance")

        try:

            with self.db.get_connection() as conn:

                cursor = conn.cursor()

                cursor.execute(

                    f"""
                    SELECT {column}
                    FROM {table}
                    WHERE student_id = ? AND subject = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,

                    (student_id, subject),

                )

                row = cursor.fetchone()

        except Exception:

            self.logger.exception(

                "Failed to check recent database marks | student_id=%s | subject=%s",

                student_id,

                subject,

            )

            return None



        if not row or not row[0]:

            return None



        try:

            return datetime.strptime(str(row[0]), config.REPORT_DATETIME_FORMAT)

        except ValueError:

            return None



    def _log_attendance_event(

        self,

        event_type: str,

        name: str,

        roll_number: str,

        student_id: str,

        subject: str,

        mark_time: str,

        confidence: float,

    ):

        self.logger.info(

            "Attendance event | event=%s | name=%s | roll=%s | student_id=%s | subject=%s | time=%s | confidence=%.2f | camera=%s",

            event_type,

            name,

            roll_number,

            student_id,

            subject,

            mark_time,

            confidence,

            self.camera_name,

        )



    def _draw_detections(self, frame: np.ndarray, detections: List[FaceDetectionResult]):

        subject = self._get_active_subject()

        header = f"{self.camera_name} [{self.camera_role.upper()}] | Subject: {subject} | Press q to quit"

        cv2.putText(

            frame,

            header,

            (10, 24),

            cv2.FONT_HERSHEY_SIMPLEX,

            0.55,

            config.COLOR_WHITE,

            2,

        )



        for detection in detections:

            top, right, bottom, left = detection.bbox

            if detection.is_recognized:

                color = config.COLOR_GREEN

                if detection.status in {"Already inside", "No active entry", "Duplicate blocked"}:

                    color = config.COLOR_BLUE

            else:

                color = config.COLOR_RED



            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)



            text = f"{detection.name} ({detection.confidence:.1f}%)"

            if detection.status:

                text = f"{text} | {detection.status}"



            text_origin_y = top - 10 if top - 10 > 20 else bottom + 20

            cv2.putText(

                frame,

                text,

                (left, text_origin_y),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.5,

                color,

                2,

            )

