"""Shared face recognition pipeline for web and camera modules."""

from __future__ import annotations

import base64
import os
import pickle
from typing import Dict, List, Optional, Tuple

import cv2
import face_recognition
import numpy as np

from . import config


FaceLocation = Tuple[int, int, int, int]


class RecognitionService:
    """Loads encodings and performs optimized recognition from frames/base64 images."""

    def __init__(self):
        self.encodings_file = config.ENCODINGS_FILE
        self.known_encodings: List[np.ndarray] = []
        self.known_names: List[str] = []
        self._encodings_mtime: Optional[float] = None
        self._yolo_model = None
        self._yolo_supported = False
        self._yolo_active = False

        self.load_encodings(force=True)
        self._initialize_yolo()

    @property
    def yolo_supported(self) -> bool:
        return self._yolo_supported

    @property
    def yolo_active(self) -> bool:
        return self._yolo_active

    def _initialize_yolo(self):
        if not config.ENABLE_YOLO_IF_AVAILABLE:
            return

        model_path = config.YOLO_MODEL_PATH
        if not os.path.exists(model_path):
            return

        try:
            from ultralytics import YOLO  # type: ignore
        except Exception:
            return

        try:
            self._yolo_model = YOLO(model_path)
            self._yolo_supported = True
            self._yolo_active = True
        except Exception:
            self._yolo_model = None
            self._yolo_supported = False
            self._yolo_active = False

    def set_yolo_active(self, enabled: bool) -> bool:
        """Enable YOLO only if model/runtime is available."""
        self._yolo_active = bool(enabled) and self._yolo_supported
        return self._yolo_active

    def load_encodings(self, force: bool = False) -> bool:
        """Load or reload encodings if file changes."""
        if not os.path.exists(self.encodings_file):
            self.known_encodings = []
            self.known_names = []
            self._encodings_mtime = None
            return False

        mtime = os.path.getmtime(self.encodings_file)
        if not force and self._encodings_mtime == mtime and self.known_encodings:
            return True

        try:
            with open(self.encodings_file, "rb") as file_handle:
                data = pickle.load(file_handle)

            self.known_encodings = data.get("encodings", [])
            self.known_names = data.get("names", [])
            self._encodings_mtime = mtime
            return bool(self.known_encodings)
        except Exception:
            self.known_encodings = []
            self.known_names = []
            self._encodings_mtime = None
            return False

    def decode_base64_image(self, image_data: str) -> Optional[np.ndarray]:
        """Decode a browser-captured base64 image into an OpenCV frame."""
        if not image_data:
            return None

        encoded = image_data.split(",", 1)[1] if "," in image_data else image_data
        try:
            image_bytes = base64.b64decode(encoded)
            np_bytes = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(np_bytes, cv2.IMREAD_COLOR)
            return frame
        except Exception:
            return None

    def recognize_from_base64(self, image_data: str) -> Optional[Dict]:
        frame = self.decode_base64_image(image_data)
        if frame is None:
            return None
        return self.recognize_from_frame(frame)

    def recognize_from_frame(self, frame: np.ndarray) -> Optional[Dict]:
        if not self.load_encodings():
            return None

        scale = config.RECOGNITION_FRAME_SCALE
        if 0 < scale < 1:
            small_frame = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
        else:
            small_frame = frame

        rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        face_locations = self._detect_faces(rgb_frame)
        match = self._match_from_locations(rgb_frame, face_locations, scale)
        if match:
            return match

        # If YOLO is active but failed to produce a stable recognition, retry with
        # the native face_recognition detector as a safety fallback.
        if self._yolo_active:
            fallback_locations = face_recognition.face_locations(
                rgb_frame, model=config.FACE_DETECTION_MODEL
            )
            match = self._match_from_locations(rgb_frame, fallback_locations, scale)
            if match:
                return match

        return None

    def _match_from_locations(
        self, rgb_frame: np.ndarray, face_locations: List[FaceLocation], scale: float
    ) -> Optional[Dict]:
        if not face_locations:
            return None

        try:
            face_encodings = face_recognition.face_encodings(
                rgb_frame, face_locations, model=config.FACE_ENCODING_MODEL
            )
        except Exception:
            return None

        if not face_encodings:
            return None

        for location, face_encoding in zip(face_locations, face_encodings):
            face_distances = face_recognition.face_distance(
                self.known_encodings, face_encoding
            )
            if len(face_distances) == 0:
                continue

            best_idx = int(np.argmin(face_distances))
            best_distance = float(face_distances[best_idx])
            if best_distance > config.FACE_RECOGNITION_TOLERANCE:
                continue

            student_id = self.known_names[best_idx]
            name = self._extract_name(student_id)
            confidence = max(0.0, min(100.0, (1 - best_distance) * 100))
            bbox = self._restore_bbox_to_original_scale(location, scale)

            return {
                "student_id": student_id,
                "name": name,
                "confidence": round(confidence, 2),
                "bbox": bbox,
                "distance": best_distance,
            }

        return None

    def get_runtime_info(self) -> Dict:
        return {
            "encodings_loaded": len(self.known_encodings),
            "students_loaded": len(set(self.known_names)),
            "yolo_supported": self.yolo_supported,
            "yolo_active": self.yolo_active,
        }

    def _detect_faces(self, rgb_frame: np.ndarray) -> List[FaceLocation]:
        if self._yolo_active and self._yolo_model is not None:
            yolo_locations = self._detect_faces_with_yolo(rgb_frame)
            if yolo_locations:
                return yolo_locations

        return face_recognition.face_locations(
            rgb_frame, model=config.FACE_DETECTION_MODEL
        )

    def _detect_faces_with_yolo(self, rgb_frame: np.ndarray) -> List[FaceLocation]:
        try:
            results = self._yolo_model.predict(
                source=rgb_frame,
                verbose=False,
                conf=config.YOLO_CONFIDENCE_THRESHOLD,
            )
            if not results:
                return []

            boxes = results[0].boxes
            if boxes is None or boxes.xyxy is None:
                return []

            height, width = rgb_frame.shape[:2]
            locations: List[FaceLocation] = []

            for box in boxes.xyxy.cpu().numpy().tolist():
                x1, y1, x2, y2 = box[:4]
                left = max(0, int(x1))
                top = max(0, int(y1))
                right = min(width, int(x2))
                bottom = min(height, int(y2))

                if right <= left or bottom <= top:
                    continue

                locations.append((top, right, bottom, left))

            return locations
        except Exception:
            return []

    @staticmethod
    def _extract_name(student_id: str) -> str:
        parts = student_id.split("_")
        if len(parts) >= 3:
            return " ".join(parts[2:])
        return student_id

    @staticmethod
    def _restore_bbox_to_original_scale(
        bbox: FaceLocation, scale: float
    ) -> FaceLocation:
        if scale <= 0 or scale == 1:
            return bbox

        top, right, bottom, left = bbox
        multiplier = 1 / scale
        return (
            int(top * multiplier),
            int(right * multiplier),
            int(bottom * multiplier),
            int(left * multiplier),
        )
