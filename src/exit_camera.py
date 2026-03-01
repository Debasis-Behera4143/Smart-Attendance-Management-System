"""
Exit Camera System
Detects and recognizes students leaving and records attendance status.
Supports USB cameras, RTSP, RTMP, and IP camera streams (CCTV-ready)
"""

import time

import cv2

from . import config
from .attendance_manager import AttendanceManager
from .database_manager import DatabaseManager
from .recognition_service import RecognitionService
from .camera_source import CameraSource


class ExitCameraSystem:
    """Manages exit point face recognition and attendance marking."""

    def __init__(self):
        # Use new camera source (supports CCTV)
        self.camera_source = config.CAMERA_EXIT_SOURCE
        # Legacy fallback
        if self.camera_source == "0":
            self.camera_source = str(config.CAMERA_EXIT_ID)
        self.db = DatabaseManager()
        self.attendance_mgr = AttendanceManager()
        self.recognizer = RecognitionService()

    def process_exit(self, student_id: str, name: str, confidence: float) -> bool:
        active_subject = self.db.get_setting("active_subject", config.DEFAULT_SUBJECT)
        exit_result = self.db.mark_exit_and_save_attendance(
            student_id=student_id,
            name=name,
            minimum_duration=self.attendance_mgr.minimum_duration,
            subject=active_subject,
        )
        if not exit_result:
            print("\n" + "⚠" * 60)
            print(f"NO ACTIVE ENTRY FOUND FOR {name.upper()}")
            print("⚠" * 60)
            print(f"Current Subject: {active_subject}")
            print(f"Student ID: {student_id}")
            print("\nPossible reasons:")
            print("  • Student hasn't marked entry for this subject")
            print("  • Subject setting changed since entry")
            print("  • Entry was for a different subject")
            print("⚠" * 60 + "\n")
            return False

        print("\n" + "=" * 60)
        print("✓ EXIT MARKED - ATTENDANCE RECORDED")
        print("=" * 60)
        print(f"  Student ID : {student_id}")
        print(f"  Name       : {name}")
        print(f"  Subject    : {exit_result.get('subject', active_subject)}")
        print(f"  Entry Time : {exit_result['entry_time']}")
        print(f"  Exit Time  : {exit_result['exit_time']}")
        print(f"  Duration   : {exit_result['duration']} minutes")
        print(f"  Status     : {exit_result['status']}")
        print(f"  Confidence : {confidence:.2f}%")
        print(f"  Date       : {exit_result['date']}")
        print("=" * 60 + "\n")
        return True

    def run(self):
        print("\n" + "=" * 60)
        print("EXIT CAMERA SYSTEM")
        print("=" * 60)

        if not self.recognizer.known_encodings:
            print("No encodings loaded. Generate encodings first.")
            return

        # Initialize camera using CameraSource abstraction (CCTV-ready)
        print("\nInitializing camera...")
        camera = CameraSource(source=self.camera_source, name="Exit Camera")
        
        if not camera.open():
            print("✗ Error: Could not open camera!")
            print("\nTroubleshooting:")
            print("  - For USB camera: Set SMART_ATTENDANCE_CAMERA_EXIT_SOURCE=0")
            print("  - For RTSP: Set SMART_ATTENDANCE_CAMERA_EXIT_SOURCE=rtsp://user:pass@ip:port/stream")
            print("  - For IP Camera: Set SMART_ATTENDANCE_CAMERA_EXIT_SOURCE=http://ip:port/video")
            return

        camera.set_resolution(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)

        active_subject = self.db.get_setting("active_subject", config.DEFAULT_SUBJECT)
        print(f"\n✓ Camera initialized successfully")
        print(f"Active Subject: {active_subject}")
        print("System active. Press 'q' to quit.\n")
        last_student_id = None
        last_seen_at = 0.0
        reconnect_attempts = 0

        try:
            while True:
                ok, frame = camera.read()
                if not ok or frame is None:
                    print("⚠ Failed to read frame from camera")
                    
                    # Attempt reconnection for network streams (CCTV)
                    if camera.source_type in ["RTSP", "RTMP", "HTTP", "IP_CAMERA"]:
                        if reconnect_attempts < config.CAMERA_RECONNECT_ATTEMPTS:
                            reconnect_attempts += 1
                            print(f"⟳ Reconnection attempt {reconnect_attempts}/{config.CAMERA_RECONNECT_ATTEMPTS}...")
                            time.sleep(config.CAMERA_RECONNECT_DELAY_SECONDS)
                            if camera.reconnect():
                                print("✓ Reconnected successfully")
                                reconnect_attempts = 0
                                continue
                        else:
                            print("✗ Maximum reconnection attempts reached")
                            break
                    else:
                        print("Failed to capture frame.")
                        break
                
                # Reset reconnect attempts on successful read
                reconnect_attempts = 0

                match = self.recognizer.recognize_from_frame(frame)
                if match:
                    student_id = match["student_id"]
                    name = match["name"]
                    confidence = match["confidence"]
                    top, right, bottom, left = match["bbox"]

                    # Avoid duplicate processing in very short windows.
                    now = time.time()
                    if student_id != last_student_id or (now - last_seen_at) > 2.0:
                        self.process_exit(student_id, name, confidence)
                        last_student_id = student_id
                        last_seen_at = now

                    cv2.rectangle(frame, (left, top), (right, bottom), config.COLOR_BLUE, 2)
                    label = f"{name} ({confidence:.1f}%)"
                    cv2.rectangle(
                        frame,
                        (left, bottom - 35),
                        (right, bottom),
                        config.COLOR_BLUE,
                        cv2.FILLED,
                    )
                    cv2.putText(
                        frame,
                        label,
                        (left + 6, bottom - 8),
                        cv2.FONT_HERSHEY_DUPLEX,
                        0.5,
                        config.COLOR_WHITE,
                        1,
                    )

                # Display subject and status on screen
                cv2.putText(
                    frame,
                    f"Subject: {active_subject}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    config.COLOR_GREEN,
                    2,
                )
                cv2.putText(
                    frame,
                    "EXIT CAMERA - Ready to mark exit",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    config.COLOR_WHITE,
                    1,
                )

                cv2.putText(
                    frame,
                    "Press q to quit",
                    (10, frame.shape[0] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    config.COLOR_WHITE,
                    1,
                )
                cv2.imshow("Exit Camera System", frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break

        except KeyboardInterrupt:
            pass
        finally:
            camera.close()
            cv2.destroyAllWindows()
            print("\nExit camera system stopped.")


def main():
    system = ExitCameraSystem()
    system.run()


if __name__ == "__main__":
    main()
