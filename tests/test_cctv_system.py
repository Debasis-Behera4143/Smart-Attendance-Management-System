"""Automated smoke tests for CCTV attendance integration."""



from __future__ import annotations



import argparse

import threading

import time

import unittest

from datetime import datetime, timedelta

from unittest.mock import Mock



import numpy as np



import run_cctv_system

from src.cctv_stream_processor import CCTVStreamProcessor, FaceDetectionResult

from src.threaded_camera_capture import ThreadedCameraCapture





class CCTVProcessorTests(unittest.TestCase):

    def _make_processor(self, role: str = "entry") -> CCTVStreamProcessor:

        return CCTVStreamProcessor(

            stream_url="0",

            camera_role=role,

            camera_name=f"Test-{role}",

            show_live_display=False,

        )



    def test_match_face_returns_unknown_when_no_known_encodings(self):

        processor = self._make_processor("entry")

        processor.recognizer.known_encodings = []

        processor.recognizer.known_names = []



        result = processor._match_face((0, 10, 10, 0), np.zeros((128,), dtype=np.float64))



        self.assertFalse(result.is_recognized)

        self.assertIsNone(result.student_id)

        self.assertEqual(result.name, "Unknown")



    def test_duplicate_cache_blocks_within_window(self):

        processor = self._make_processor("entry")

        processor._get_last_db_mark_time = Mock(return_value=None)

        now = datetime.now()

        processor._remember_mark("student_1", "Operating System", now)



        blocked = processor._is_duplicate_recent(

            "student_1",

            "Operating System",

            now + timedelta(seconds=1),

        )

        not_blocked = processor._is_duplicate_recent(

            "student_1",

            "Operating System",

            now + timedelta(seconds=processor.duplicate_window_seconds + 1),

        )



        self.assertTrue(blocked)

        self.assertFalse(not_blocked)



    def test_mark_attendance_entry_success(self):

        processor = self._make_processor("entry")

        processor._is_duplicate_recent = Mock(return_value=False)



        db_mock = Mock()

        db_mock.get_setting.return_value = "Operating System"

        db_mock.get_student_info.return_value = (

            "student_001_john",

            "John",

            "R001",

            "2026-03-12",

        )

        db_mock.mark_entry.return_value = {

            "entry_id": 1,

            "entry_time": "2026-03-12 09:10:00",

            "subject": "Operating System",

        }

        processor.db = db_mock



        status = processor._mark_attendance(

            FaceDetectionResult(

                bbox=(0, 0, 0, 0),

                name="John",

                student_id="student_001_john",

                confidence=88.2,

                is_recognized=True,

            )

        )



        self.assertEqual(status, "Entry marked")

        db_mock.mark_entry.assert_called_once()



    def test_mark_attendance_blocks_duplicate_early(self):

        processor = self._make_processor("entry")

        processor._is_duplicate_recent = Mock(return_value=True)

        db_mock = Mock()

        processor.db = db_mock



        status = processor._mark_attendance(

            FaceDetectionResult(

                bbox=(0, 0, 0, 0),

                name="John",

                student_id="student_001_john",

                confidence=90.0,

                is_recognized=True,

            )

        )



        self.assertEqual(status, "Duplicate blocked")

        db_mock.get_student_info.assert_not_called()



    def test_mark_attendance_exit_without_active_entry(self):

        processor = self._make_processor("exit")

        processor._is_duplicate_recent = Mock(return_value=False)

        processor._get_minimum_duration = Mock(return_value=60)



        db_mock = Mock()

        db_mock.get_setting.return_value = "Operating System"

        db_mock.get_student_info.return_value = (

            "student_001_john",

            "John",

            "R001",

            "2026-03-12",

        )

        db_mock.mark_exit_and_save_attendance.return_value = None

        processor.db = db_mock



        status = processor._mark_attendance(

            FaceDetectionResult(

                bbox=(0, 0, 0, 0),

                name="John",

                student_id="student_001_john",

                confidence=92.0,

                is_recognized=True,

            )

        )



        self.assertEqual(status, "No active entry")

        db_mock.mark_exit_and_save_attendance.assert_called_once()



    def test_run_exits_immediately_on_empty_stream(self):

        processor = CCTVStreamProcessor(

            stream_url="",

            camera_role="entry",

            camera_name="NoStream",

            show_live_display=False,

        )

        done = threading.Event()



        def target():

            processor.run()

            done.set()



        thread = threading.Thread(target=target, daemon=True)

        thread.start()

        thread.join(timeout=2.0)



        self.assertTrue(done.is_set())



    def test_active_subject_setting_is_cached_briefly(self):

        processor = self._make_processor("entry")

        db_mock = Mock()

        db_mock.get_setting.return_value = "Operating System"

        processor.db = db_mock



        first = processor._get_active_subject()

        second = processor._get_active_subject()



        self.assertEqual(first, "Operating System")

        self.assertEqual(second, "Operating System")

        db_mock.get_setting.assert_called_once_with("active_subject", "Operating System")





class ThreadedCameraCaptureTests(unittest.TestCase):

    def test_get_latest_frame_can_return_same_reference_without_copy(self):

        capture = ThreadedCameraCapture("0", "Test Camera", Mock())

        frame = np.zeros((4, 4, 3), dtype=np.uint8)

        capture.latest_frame = frame

        capture.last_frame_time = time.time()



        ok, returned = capture.get_latest_frame(copy=False, max_age_seconds=10.0)



        self.assertTrue(ok)

        self.assertIs(returned, frame)



    def test_get_latest_frame_rejects_stale_frame(self):

        capture = ThreadedCameraCapture("0", "Test Camera", Mock())

        capture.latest_frame = np.zeros((4, 4, 3), dtype=np.uint8)

        capture.last_frame_time = time.time() - 5.0



        ok, returned = capture.get_latest_frame(copy=False, max_age_seconds=1.0)



        self.assertFalse(ok)

        self.assertIsNone(returned)





class CCTVRunnerTests(unittest.TestCase):

    def test_resolve_streams_with_explicit_values(self):

        args = argparse.Namespace(

            mode="both",

            entry_stream="rtsp://entry",

            exit_stream="http://exit",

            subject=None,

            no_display=True,

        )

        entry, exit_ = run_cctv_system._resolve_streams(args)

        self.assertEqual(entry, "rtsp://entry")

        self.assertEqual(exit_, "http://exit")



    def test_resolve_streams_honors_mode_entry(self):

        args = argparse.Namespace(

            mode="entry",

            entry_stream="rtsp://entry",

            exit_stream="http://exit",

            subject=None,

            no_display=True,

        )

        entry, exit_ = run_cctv_system._resolve_streams(args)

        self.assertEqual(entry, "rtsp://entry")

        self.assertEqual(exit_, "")





if __name__ == "__main__":

    unittest.main()

