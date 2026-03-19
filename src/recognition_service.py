"""Shared face recognition pipeline for web and camera modules."""



from __future__ import annotations



import base64

import os

import pickle

import time

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

        self.known_encodings_matrix = np.empty((0, 128), dtype=np.float64)

        self._encodings_mtime: Optional[float] = None

        self._last_encodings_check_at = 0.0

        self._encodings_check_interval_seconds = max(0.0, config.ENCODINGS_RELOAD_CHECK_SECONDS)

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

            from ultralytics import YOLO

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

        now = time.monotonic()

        if (

            not force

            and self._encodings_check_interval_seconds > 0

            and (now - self._last_encodings_check_at) < self._encodings_check_interval_seconds

        ):

            return bool(self.known_encodings)

        self._last_encodings_check_at = now



        if not os.path.exists(self.encodings_file):

            self.known_encodings = []

            self.known_names = []

            self.known_encodings_matrix = np.empty((0, 128), dtype=np.float64)

            self._encodings_mtime = None

            return False



        mtime = os.path.getmtime(self.encodings_file)

        if not force and self._encodings_mtime == mtime and self.known_encodings:

            return True



        try:

            with open(self.encodings_file, "rb") as file_handle:

                data = pickle.load(file_handle)



            raw_encodings = data.get("encodings", []) or []

            raw_names = data.get("names", []) or []



            valid_encodings: List[np.ndarray] = []

            valid_names: List[str] = []

            for name, encoding in zip(raw_names, raw_encodings):

                try:

                    vector = np.asarray(encoding, dtype=np.float64).reshape(-1)

                except Exception:

                    continue

                if vector.shape != (128,):

                    continue

                valid_encodings.append(vector)

                valid_names.append(str(name))



            self.known_encodings = valid_encodings

            self.known_names = valid_names

            self.known_encodings_matrix = (

                np.vstack(valid_encodings)

                if valid_encodings

                else np.empty((0, 128), dtype=np.float64)

            )

            self._encodings_mtime = mtime

            return bool(self.known_encodings)

        except Exception:

            self.known_encodings = []

            self.known_names = []

            self.known_encodings_matrix = np.empty((0, 128), dtype=np.float64)

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



        prepared_frame = self._prepare_frame(frame)

        if prepared_frame is None:

            return None



        primary_scale = config.RECOGNITION_FRAME_SCALE

        scales = [primary_scale]

        if primary_scale != 0.75:

            scales.append(0.75)



        for scale in scales:

            match = self._recognize_at_scale(prepared_frame, scale)

            if match:

                return match



        return None



    def _prepare_frame(self, frame: np.ndarray) -> Optional[np.ndarray]:

        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:

            return None



        if frame.ndim == 2:

            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)



        max_width = max(320, int(config.RECOGNITION_MAX_FRAME_WIDTH))

        height, width = frame.shape[:2]

        if width > max_width:

            ratio = max_width / float(width)

            resized_height = max(1, int(height * ratio))

            return cv2.resize(frame, (max_width, resized_height))



        return frame



    def _recognize_at_scale(self, frame: np.ndarray, scale: float) -> Optional[Dict]:

        if 0 < scale < 1:

            scaled_frame = cv2.resize(frame, (0, 0), fx=scale, fy=scale)

        else:

            scaled_frame = frame



        rgb_frame = cv2.cvtColor(scaled_frame, cv2.COLOR_BGR2RGB)



        preferred_model = str(config.FACE_DETECTION_MODEL or "hog").strip().lower()

        best_hog_match: Optional[Dict] = None



        hog_locations = face_recognition.face_locations(rgb_frame, model="hog")

        if hog_locations:

            best_hog_match = self._match_from_locations(rgb_frame, hog_locations, scale, strict=True)

            if best_hog_match and best_hog_match.get("distance", 1.0) < 0.45:

                return best_hog_match



            if preferred_model == "hog":

                relaxed_hog_match = self._match_from_locations(rgb_frame, hog_locations, scale, strict=False)

                if relaxed_hog_match:

                    return relaxed_hog_match



        if preferred_model == "cnn":

            cnn_locations = face_recognition.face_locations(rgb_frame, model="cnn")

            cnn_match = self._match_from_locations(rgb_frame, cnn_locations, scale, strict=False)

            if cnn_match:

                return cnn_match



        if self._yolo_active:

            yolo_locations = self._detect_faces_with_yolo(rgb_frame)

            if yolo_locations:

                yolo_match = self._match_from_locations(rgb_frame, yolo_locations, scale, strict=False)

                if yolo_match:

                    return yolo_match



        return best_hog_match



    def _match_from_locations(

        self, rgb_frame: np.ndarray, face_locations: List[FaceLocation], scale: float, strict: bool = False

    ) -> Optional[Dict]:

        if not face_locations or self.known_encodings_matrix.size == 0:

            return None



        try:

            face_encodings = face_recognition.face_encodings(

                rgb_frame, face_locations, model=config.FACE_ENCODING_MODEL

            )

        except Exception:

            return None



        if not face_encodings:

            return None



        primary_threshold = (

            config.FACE_RECOGNITION_TOLERANCE * 0.9

            if strict

            else config.FACE_RECOGNITION_TOLERANCE

        )

        best_match = self._best_match_for_threshold(

            face_locations=face_locations,

            face_encodings=face_encodings,

            scale=scale,

            threshold=primary_threshold,

        )

        if best_match or strict:

            return best_match



        relaxed_tolerance = min(0.60, config.FACE_RECOGNITION_TOLERANCE + 0.10)

        return self._best_match_for_threshold(

            face_locations=face_locations,

            face_encodings=face_encodings,

            scale=scale,

            threshold=relaxed_tolerance,

        )



    def _best_match_for_threshold(

        self,

        *,

        face_locations: List[FaceLocation],

        face_encodings: List[np.ndarray],

        scale: float,

        threshold: float,

    ) -> Optional[Dict]:

        best_candidate: Optional[Dict] = None



        for location, face_encoding in zip(face_locations, face_encodings):

            face_distances = face_recognition.face_distance(

                self.known_encodings_matrix,

                face_encoding,

            )

            if len(face_distances) == 0:

                continue



            best_idx = int(np.argmin(face_distances))

            best_distance = float(face_distances[best_idx])

            if best_distance > threshold:

                continue



            candidate = self._build_match_result(

                student_id=self.known_names[best_idx],

                bbox=location,

                scale=scale,

                distance=best_distance,

            )



            if best_candidate is None or candidate["distance"] < best_candidate["distance"]:

                best_candidate = candidate



        return best_candidate



    def _build_match_result(

        self,

        *,

        student_id: str,

        bbox: FaceLocation,

        scale: float,

        distance: float,

    ) -> Dict:

        name = self._extract_name(student_id)

        confidence = max(0.0, min(100.0, (1 - distance) * 100))

        return {

            "student_id": student_id,

            "name": name,

            "confidence": round(confidence, 2),

            "bbox": self._restore_bbox_to_original_scale(bbox, scale),

            "distance": distance,

        }



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

