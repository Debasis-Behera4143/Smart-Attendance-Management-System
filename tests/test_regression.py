import base64
import importlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

from PIL import Image

import src.config as config
from src.attendance_manager import AttendanceManager
from src.database_manager import DatabaseManager
from src.validators import (
    ValidationError,
    validate_roll_number,
    validate_student_id,
)


class TempConfigMixin:
    CONFIG_KEYS = (
        "DATA_DIR",
        "DATASET_PATH",
        "ENCODINGS_PATH",
        "DATABASE_PATH",
        "LOGS_PATH",
        "REPORTS_PATH",
        "DATABASE_FILE",
        "LOG_FILE",
        "ENCODINGS_FILE",
        "YOLO_MODEL_PATH",
        "ENABLE_YOLO_IF_AVAILABLE",
        "REQUIRE_API_KEY",
        "API_KEY",
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._original_config = {key: getattr(config, key) for key in cls.CONFIG_KEYS}
        cls.temp_root = tempfile.mkdtemp(prefix="smart_attendance_regression_")
        cls._set_temp_paths(cls.temp_root)

    @classmethod
    def tearDownClass(cls):
        for key, value in cls._original_config.items():
            setattr(config, key, value)
        shutil.rmtree(cls.temp_root, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def _set_temp_paths(cls, root: str):
        data_dir = os.path.join(root, "data")
        dataset_path = os.path.join(data_dir, "dataset")
        encodings_path = os.path.join(data_dir, "encodings")
        database_path = os.path.join(data_dir, "database")
        logs_path = os.path.join(data_dir, "logs")
        reports_path = os.path.join(data_dir, "reports")
        models_path = os.path.join(root, "models")

        os.makedirs(dataset_path, exist_ok=True)
        os.makedirs(encodings_path, exist_ok=True)
        os.makedirs(database_path, exist_ok=True)
        os.makedirs(logs_path, exist_ok=True)
        os.makedirs(reports_path, exist_ok=True)
        os.makedirs(models_path, exist_ok=True)

        config.DATA_DIR = data_dir
        config.DATASET_PATH = dataset_path
        config.ENCODINGS_PATH = encodings_path
        config.DATABASE_PATH = database_path
        config.LOGS_PATH = logs_path
        config.REPORTS_PATH = reports_path
        config.DATABASE_FILE = os.path.join(database_path, "attendance.db")
        config.LOG_FILE = os.path.join(logs_path, "system_logs.txt")
        config.ENCODINGS_FILE = os.path.join(encodings_path, "face_encodings.pkl")
        config.YOLO_MODEL_PATH = os.path.join(models_path, "missing.pt")
        config.ENABLE_YOLO_IF_AVAILABLE = False
        config.REQUIRE_API_KEY = False
        config.API_KEY = ""


class AttendanceAndValidatorTests(unittest.TestCase):
    def test_attendance_manager_calculates_duration_and_status(self):
        manager = AttendanceManager()
        duration = manager.calculate_duration(
            "2026-02-26 09:00:00",
            "2026-02-26 10:45:00",
        )
        self.assertEqual(duration, 105)
        self.assertEqual(manager.determine_status(duration), "PRESENT")

    def test_attendance_manager_rejects_reverse_timestamps(self):
        manager = AttendanceManager()
        with self.assertRaises(ValueError):
            manager.calculate_duration(
                "2026-02-26 11:00:00",
                "2026-02-26 10:59:59",
            )

    def test_roll_number_auto_format(self):
        self.assertEqual(validate_roll_number("ROLL-2301 105 473"), "2301105473")

    def test_student_id_validation_blocks_path_sequences(self):
        with self.assertRaises(ValidationError):
            validate_student_id("student_123_..\\admin")


class DatabaseManagerRegressionTests(TempConfigMixin, unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attendance")
            cursor.execute("DELETE FROM exit_log")
            cursor.execute("DELETE FROM entry_log")
            cursor.execute("DELETE FROM students")
            conn.commit()

    def test_entry_exit_and_attendance_flow(self):
        student_id = "student_001_Alice"
        name = "Alice"

        self.assertTrue(self.db.register_student(student_id, name, "001"))

        entry_id = self.db.mark_entry(student_id, name)
        self.assertIsNotNone(entry_id)

        duplicate_entry_id = self.db.mark_entry(student_id, name)
        self.assertIsNone(duplicate_entry_id)

        exit_result = self.db.mark_exit_and_save_attendance(
            student_id=student_id,
            name=name,
            minimum_duration=0,
            subject="Data Science",
        )
        self.assertIsNotNone(exit_result)
        self.assertEqual(exit_result["status"], "PRESENT")
        self.assertEqual(exit_result["subject"], "Data Science")

        records = self.db.get_attendance_filtered(student_id=student_id)[0]
        self.assertEqual(len(records), 1)

        no_active_entry = self.db.mark_exit_and_save_attendance(
            student_id=student_id,
            name=name,
            minimum_duration=0,
            subject="Data Science",
        )
        self.assertIsNone(no_active_entry)

    def test_upsert_attendance_updates_existing_row(self):
        student_id = "student_002_Bob"
        name = "Bob"
        self.assertTrue(self.db.register_student(student_id, name, "002"))

        date = "2026-02-26"
        entry_time = "2026-02-26 09:00:00"

        self.assertTrue(
            self.db.upsert_attendance(
                student_id=student_id,
                name=name,
                entry_time=entry_time,
                exit_time="2026-02-26 09:30:00",
                duration=30,
                status="ABSENT",
                date=date,
                subject="Machine Learning",
            )
        )
        self.assertTrue(
            self.db.upsert_attendance(
                student_id=student_id,
                name=name,
                entry_time=entry_time,
                exit_time="2026-02-26 11:30:00",
                duration=150,
                status="PRESENT",
                date=date,
                subject="Machine Learning",
            )
        )

        records, total = self.db.get_attendance_filtered(student_id=student_id)
        self.assertEqual(total, 1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0][4], 150)
        self.assertEqual(records[0][5], "PRESENT")


class WebApiRegressionTests(TempConfigMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        sys.modules.pop("web.app", None)
        cls.web = importlib.import_module("web.app")
        cls.client = cls.web.app.test_client()

    def setUp(self):
        self._reset_db()
        self.web.rate_limiter._requests.clear()
        self._clear_dir(config.DATASET_PATH)
        self._clear_dir(config.REPORTS_PATH)

    def _reset_db(self):
        with self.web.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attendance")
            cursor.execute("DELETE FROM exit_log")
            cursor.execute("DELETE FROM entry_log")
            cursor.execute("DELETE FROM students")
            conn.commit()

    def _clear_dir(self, path: str):
        for name in os.listdir(path):
            full = os.path.join(path, name)
            if os.path.isdir(full):
                shutil.rmtree(full, ignore_errors=True)
            else:
                os.remove(full)

    @staticmethod
    def _make_base64_jpeg_data_url() -> str:
        image = Image.new("RGB", (20, 20), color=(10, 200, 20))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    def _register_student(self, student_id="student_100_TestUser", name="TestUser", roll="100"):
        response = self.client.post(
            "/api/register-student",
            json={
                "student_id": student_id,
                "name": name,
                "roll_number": roll,
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return student_id, name

    def test_page_routes_return_200(self):
        for route in ("/", "/dashboard", "/register", "/entry", "/exit", "/reports", "/student-attendance"):
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200, route)

    def test_health_endpoint(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertIn("runtime", payload)
        self.assertIn("settings", payload)

    def test_settings_roundtrip(self):
        post_response = self.client.post(
            "/api/settings",
            json={
                "camera_policy": "always_on",
                "camera_run_mode": "interval",
                "active_subject": "Data Science",
                "run_interval_seconds": 15,
                "session_duration_minutes": 120,
                "fair_motion_threshold": 0.05,
                "use_yolo": False,
            },
        )
        self.assertEqual(post_response.status_code, 200)

        get_response = self.client.get("/api/settings")
        self.assertEqual(get_response.status_code, 200)
        settings = get_response.get_json()["settings"]
        self.assertEqual(settings["camera_policy"], "always_on")
        self.assertEqual(settings["camera_run_mode"], "interval")
        self.assertEqual(settings["active_subject"], "Data Science")
        self.assertEqual(settings["run_interval_seconds"], 15)

    def test_register_student_duplicate_conflict(self):
        self._register_student()
        duplicate = self.client.post(
            "/api/register-student",
            json={
                "student_id": "student_100_TestUser",
                "name": "TestUser",
                "roll_number": "100",
            },
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_mark_entry_and_exit_flow(self):
        student_id, name = self._register_student()

        entry = self.client.post(
            "/api/mark-entry",
            json={"student_id": student_id, "name": name},
        )
        self.assertEqual(entry.status_code, 200, entry.get_data(as_text=True))

        exit_resp = self.client.post(
            "/api/mark-exit",
            json={"student_id": student_id, "name": name, "subject": "Data Science"},
        )
        self.assertEqual(exit_resp.status_code, 200, exit_resp.get_data(as_text=True))
        exit_payload = exit_resp.get_json()
        self.assertEqual(exit_payload["subject"], "Data Science")

        attendance = self.client.get(f"/api/get-attendance?student_id={student_id}")
        self.assertEqual(attendance.status_code, 200)
        attendance_payload = attendance.get_json()
        self.assertEqual(attendance_payload["total"], 1)
        self.assertEqual(len(attendance_payload["records"]), 1)

    def test_manual_attendance_rejects_bad_timestamp(self):
        student_id, name = self._register_student()
        response = self.client.post(
            "/api/manual-attendance",
            json={
                "student_id": student_id,
                "name": name,
                "entry_time": "2026/02/26 09:00",
                "exit_time": "2026-02-26 10:00:00",
                "subject": "Data Science",
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_manual_attendance_and_student_lookup(self):
        student_id, name = self._register_student()
        response = self.client.post(
            "/api/manual-attendance",
            json={
                "student_id": student_id,
                "name": name,
                "entry_time": "2026-02-26 09:00:00",
                "exit_time": "2026-02-26 11:00:00",
                "subject": "Machine Learning",
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

        lookup = self.client.get(f"/api/student-attendance?student_id={student_id}&limit=10")
        self.assertEqual(lookup.status_code, 200)
        payload = lookup.get_json()
        self.assertEqual(payload["student"]["student_id"], student_id)
        self.assertEqual(len(payload["records"]), 1)

    def test_get_attendance_pagination_and_filters(self):
        student_id, name = self._register_student()
        day_one = datetime(2026, 2, 24, 9, 0, 0)
        day_two = day_one + timedelta(days=1)

        for start in (day_one, day_two):
            entry_time = start.strftime(config.REPORT_DATETIME_FORMAT)
            exit_time = (start + timedelta(minutes=100)).strftime(config.REPORT_DATETIME_FORMAT)
            date_value = start.strftime(config.REPORT_DATE_FORMAT)
            self.assertTrue(
                self.web.db.upsert_attendance(
                    student_id=student_id,
                    name=name,
                    entry_time=entry_time,
                    exit_time=exit_time,
                    duration=100,
                    status="PRESENT",
                    date=date_value,
                    subject="Operating System",
                )
            )

        response = self.client.get(
            f"/api/get-attendance?student_id={student_id}&status=PRESENT&limit=1&offset=0"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual(len(payload["records"]), 1)

    def test_save_face_images_with_valid_payload(self):
        student_id, _ = self._register_student()
        image_payload = self._make_base64_jpeg_data_url()
        response = self.client.post(
            "/api/save-face-images",
            json={"student_id": student_id, "images": [image_payload]},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        image_path = os.path.join(config.DATASET_PATH, student_id, "img1.jpg")
        self.assertTrue(os.path.exists(image_path))

    def test_generate_encodings_endpoint_with_mock(self):
        class DummyEncoder:
            def run(self):
                return True

        with mock.patch.object(self.web, "FaceEncoder", DummyEncoder), mock.patch.object(
            self.web.recognizer, "load_encodings", return_value=True
        ) as load_mock:
            response = self.client.post("/api/generate-encodings", json={})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(load_mock.called)
        _, kwargs = load_mock.call_args
        self.assertTrue(kwargs.get("force"))

    def test_recognize_entry_and_exit_with_mocked_recognizer(self):
        student_id, name = self._register_student()
        image_payload = self._make_base64_jpeg_data_url()
        mock_match = {
            "student_id": student_id,
            "name": name,
            "confidence": 99.1,
            "bbox": (0, 10, 10, 0),
        }

        with mock.patch.object(self.web.recognizer, "recognize_from_base64", return_value=mock_match):
            entry = self.client.post("/api/recognize-entry", json={"image": image_payload})
            self.assertEqual(entry.status_code, 200, entry.get_data(as_text=True))

            exit_resp = self.client.post(
                "/api/recognize-exit",
                json={"image": image_payload, "subject": "Compiler Design"},
            )
            self.assertEqual(exit_resp.status_code, 200, exit_resp.get_data(as_text=True))
            payload = exit_resp.get_json()
            self.assertEqual(payload["subject"], "Compiler Design")

    def test_recognize_entry_returns_404_when_unrecognized(self):
        image_payload = self._make_base64_jpeg_data_url()
        with mock.patch.object(self.web.recognizer, "recognize_from_base64", return_value=None):
            response = self.client.post("/api/recognize-entry", json={"image": image_payload})
        self.assertEqual(response.status_code, 404)

    def test_generate_and_download_report(self):
        student_id, name = self._register_student()
        self.assertTrue(
            self.web.db.upsert_attendance(
                student_id=student_id,
                name=name,
                entry_time="2026-02-26 09:00:00",
                exit_time="2026-02-26 10:45:00",
                duration=105,
                status="PRESENT",
                date="2026-02-26",
                subject="Data Science",
            )
        )

        generate = self.client.post(
            "/api/generate-report",
            json={"type": "csv", "date": "2026-02-26", "subject": "Data Science"},
        )
        self.assertEqual(generate.status_code, 200, generate.get_data(as_text=True))
        file_name = generate.get_json()["file_name"]

        download = self.client.get(f"/api/download-report?file={file_name}")
        self.assertEqual(download.status_code, 200)
        disposition = download.headers.get("Content-Disposition", "")
        self.assertIn("attachment", disposition.lower())
        download.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
