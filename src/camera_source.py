"""
Camera Source Abstraction Layer
Supports multiple camera types: USB, RTSP, RTMP, HTTP, IP Cameras
Designed for future CCTV integration
"""

import cv2
import re
from typing import Optional, Tuple
from . import config


class CameraSource:
    """
    Abstraction layer for different camera sources.
    Supports:
    - USB/Webcam (device ID: 0, 1, 2...)
    - RTSP streams (rtsp://...)
    - RTMP streams (rtmp://...)
    - HTTP/MJPEG streams (http://...)
    - IP Camera streams
    """
    
    def __init__(self, source: str = "0", name: str = "Camera"):
        """
        Initialize camera source.
        
        Args:
            source: Camera source identifier
                    - Integer/string "0", "1" for USB cameras
                    - "rtsp://..." for RTSP streams
                    - "rtmp://..." for RTMP streams
                    - "http://..." for HTTP/MJPEG streams
            name: Human-readable camera name for logging
        """
        self.source = source
        self.name = name
        self.cap: Optional[cv2.VideoCapture] = None
        self.source_type = self._detect_source_type()
        
    def _detect_source_type(self) -> str:
        """Detect camera source type from identifier"""
        source_str = str(self.source).strip()
        
        # Check if it's a numeric USB camera ID
        if source_str.isdigit():
            return "USB"
        
        # Check for common stream protocols
        if source_str.startswith("rtsp://"):
            return "RTSP"
        elif source_str.startswith("rtmp://"):
            return "RTMP"
        elif source_str.startswith("http://") or source_str.startswith("https://"):
            return "HTTP"
        elif re.match(r"^\d+\.\d+\.\d+\.\d+", source_str):
            # IP address pattern
            return "IP_CAMERA"
        else:
            return "UNKNOWN"
    
    def open(self) -> bool:
        """
        Open the camera source.
        
        Returns:
            True if camera opened successfully, False otherwise
        """
        try:
            # Convert string to integer for USB cameras
            if self.source_type == "USB":
                camera_id = int(self.source)
                self.cap = cv2.VideoCapture(camera_id)
            else:
                # For network streams (RTSP, RTMP, HTTP)
                self.cap = cv2.VideoCapture(self.source)
            
            if not self.cap or not self.cap.isOpened():
                print(f"✗ Failed to open {self.source_type} camera: {self.name} ({self.source})")
                return False
            
            # Set buffer size for network streams to reduce latency
            if self.source_type in ["RTSP", "RTMP", "HTTP", "IP_CAMERA"]:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Try to read a test frame
            ret, frame = self.cap.read()
            if not ret or frame is None:
                print(f"✗ {self.source_type} camera opened but cannot read frames: {self.name}")
                self.close()
                return False
            
            # Get camera properties
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(self.cap.get(cv2.CAP_PROP_FPS))
            
            print(f"✓ {self.source_type} camera opened: {self.name}")
            print(f"  Source: {self.source}")
            print(f"  Resolution: {width}x{height} @ {fps}fps")
            
            return True
            
        except Exception as e:
            print(f"✗ Error opening camera {self.name}: {e}")
            return False
    
    def read(self) -> Tuple[bool, Optional[cv2.Mat]]:
        """
        Read a frame from the camera.
        
        Returns:
            Tuple of (success, frame)
        """
        if not self.cap or not self.cap.isOpened():
            return False, None
        
        try:
            ret, frame = self.cap.read()
            return ret, frame
        except Exception as e:
            print(f"✗ Error reading from {self.name}: {e}")
            return False, None
    
    def is_opened(self) -> bool:
        """Check if camera is currently opened"""
        return self.cap is not None and self.cap.isOpened()
    
    def close(self):
        """Release camera resources"""
        if self.cap:
            self.cap.release()
            self.cap = None
            print(f"✓ {self.name} closed")
    
    def set_resolution(self, width: int, height: int) -> bool:
        """
        Set camera resolution (may not work for network streams).
        
        Args:
            width: Frame width
            height: Frame height
            
        Returns:
            True if successful, False otherwise
        """
        if not self.cap or not self.cap.isOpened():
            return False
        
        # Resolution setting typically works for USB cameras only
        if self.source_type == "USB":
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            return True
        else:
            print(f"⚠ Resolution setting not supported for {self.source_type} streams")
            return False
    
    def reconnect(self) -> bool:
        """
        Attempt to reconnect to the camera (useful for network streams).
        
        Returns:
            True if reconnection successful, False otherwise
        """
        print(f"⟳ Attempting to reconnect {self.name}...")
        self.close()
        return self.open()
    
    def __enter__(self):
        """Context manager entry"""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    def __repr__(self):
        status = "OPEN" if self.is_opened() else "CLOSED"
        return f"CameraSource(name='{self.name}', type={self.source_type}, status={status})"


def create_camera_source(camera_config: str, name: str = "Camera") -> CameraSource:
    """
    Factory function to create camera source from configuration.
    
    Args:
        camera_config: Camera configuration (ID or URL)
        name: Camera name for logging
        
    Returns:
        CameraSource instance
        
    Examples:
        >>> cam = create_camera_source("0", "Entry Camera")
        >>> cam = create_camera_source("rtsp://admin:pass@192.168.1.100:554/stream", "CCTV Entry")
    """
    return CameraSource(source=camera_config, name=name)
