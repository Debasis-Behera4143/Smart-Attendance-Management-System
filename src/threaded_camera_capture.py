"""Threaded camera capture for USB/network streams."""



from __future__ import annotations



import threading

import time

from typing import Optional, Tuple



import cv2

import numpy as np



from . import config





class ThreadedCameraCapture:

    """Continuously reads camera frames in a background thread."""



    def __init__(self, source: str, name: str, logger):

        self.source = str(source).strip()

        self.name = name

        self.logger = logger

        self.capture: Optional[cv2.VideoCapture] = None

        self.frame_lock = threading.Lock()

        self.latest_frame: Optional[np.ndarray] = None

        self.last_frame_time: float = 0.0

        self.running = False

        self.thread: Optional[threading.Thread] = None

        self.source_type, self.cv_source = self._resolve_source(self.source)

        self.stale_frame_seconds = max(0.0, config.CAMERA_FRAME_STALE_SECONDS)



    @staticmethod

    def _resolve_source(source: str) -> Tuple[str, object]:

        source_str = source.strip()

        if source_str.isdigit():

            return "USB", int(source_str)

        if source_str.startswith("rtsp://"):

            return "RTSP", source_str

        if source_str.startswith(("http://", "https://")):

            return "HTTP", source_str

        return "STREAM", source_str



    def _open_capture(self) -> bool:

        capture = cv2.VideoCapture(self.cv_source)

        if self.source_type in {"RTSP", "HTTP", "STREAM"}:

            capture.set(cv2.CAP_PROP_BUFFERSIZE, max(1, config.CAMERA_STREAM_BUFFER_SIZE))



        if not capture.isOpened():

            self.logger.error(

                "Camera open failed | name=%s | source=%s | type=%s",

                self.name,

                self.source,

                self.source_type,

            )

            capture.release()

            return False



        self.capture = capture

        self.logger.info(

            "Camera connected | name=%s | source=%s | type=%s",

            self.name,

            self.source,

            self.source_type,

        )

        return True



    def _release_capture(self):

        if self.capture is not None:

            self.capture.release()

            self.capture = None



    def _reader_loop(self):

        while self.running:

            if not self._open_capture():

                time.sleep(max(1, config.CAMERA_RECONNECT_DELAY_SECONDS))

                continue



            read_failures = 0

            while self.running and self.capture is not None and self.capture.isOpened():

                ok, frame = self.capture.read()

                if ok and frame is not None:

                    with self.frame_lock:

                        self.latest_frame = frame

                        self.last_frame_time = time.time()

                    read_failures = 0

                    continue



                read_failures += 1

                if read_failures >= max(1, config.CAMERA_RECONNECT_ATTEMPTS):

                    self.logger.warning(

                        "Frame read failures reached limit; reconnecting | name=%s | failures=%s",

                        self.name,

                        read_failures,

                    )

                    break

                time.sleep(0.05)



            self._release_capture()

            if self.running:

                time.sleep(max(1, config.CAMERA_RECONNECT_DELAY_SECONDS))



    def start(self) -> bool:

        if self.running:

            return True

        self.running = True

        self.thread = threading.Thread(

            target=self._reader_loop,

            name=f"capture-{self.name}",

            daemon=True,

        )

        self.thread.start()

        return True



    def stop(self):

        self.running = False

        if self.thread and self.thread.is_alive():

            self.thread.join(timeout=3.0)

        self._release_capture()



    def get_latest_frame(

        self,

        *,

        copy: bool = True,

        max_age_seconds: Optional[float] = None,

    ) -> Tuple[bool, Optional[np.ndarray]]:

        with self.frame_lock:

            if self.latest_frame is None:

                return False, None



            age_limit = self.stale_frame_seconds if max_age_seconds is None else max(0.0, max_age_seconds)

            if age_limit > 0 and self.last_frame_time:

                if (time.time() - self.last_frame_time) > age_limit:

                    return False, None









            if copy:

                return True, self.latest_frame.copy()

            return True, self.latest_frame

