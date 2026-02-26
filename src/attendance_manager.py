"""
Attendance Manager
Calculates duration and determines attendance status based on entry/exit times
"""

from datetime import datetime
from typing import Optional, Tuple

from . import config


class AttendanceManager:
    """Manages attendance calculation and status determination"""
    
    def __init__(self):
        """Initialize attendance manager"""
        self.minimum_duration = config.MINIMUM_DURATION
    
    def calculate_duration(self, entry_time: str, exit_time: str) -> int:
        """
        Calculate duration in minutes between entry and exit times
        
        Args:
            entry_time: Entry timestamp in format "YYYY-MM-DD HH:MM:SS"
            exit_time: Exit timestamp in format "YYYY-MM-DD HH:MM:SS"
        
        Returns:
            Duration in minutes
        """
        # Parse timestamps
        entry_dt = datetime.strptime(entry_time, config.REPORT_DATETIME_FORMAT)
        exit_dt = datetime.strptime(exit_time, config.REPORT_DATETIME_FORMAT)

        # Validate chronology to avoid negative attendance durations
        if exit_dt < entry_dt:
            raise ValueError("exit_time cannot be earlier than entry_time")

        # Calculate difference and convert to minutes
        duration = exit_dt - entry_dt
        return int(duration.total_seconds() / 60)
    
    def determine_status(self, duration: int) -> str:
        """
        Determine attendance status based on duration
        
        Args:
            duration: Duration in minutes
        
        Returns:
            Status string: "PRESENT" or "ABSENT"
        """
        if duration >= self.minimum_duration:
            return "PRESENT"
        else:
            return "ABSENT"
    
    def calculate_attendance(
        self,
        student_id: str,
        name: str,
        entry_time: str,
        exit_time: str,
    ) -> Optional[Tuple[int, str, str]]:
        """
        Calculate complete attendance information
        
        Args:
            student_id: Student ID
            name: Student name
            entry_time: Entry timestamp
            exit_time: Exit timestamp
        
        Returns:
            Tuple of (duration, status, date) or None if error
        """
        try:
            # Calculate duration
            duration = self.calculate_duration(entry_time, exit_time)

            # Determine status
            status = self.determine_status(duration)

            # Extract date from entry time
            date = entry_time.split()[0]

            return (duration, status, date)
        except (ValueError, TypeError):
            return None
    
    def format_duration(self, minutes: int) -> str:
        """
        Format duration in a human-readable way
        
        Args:
            minutes: Duration in minutes
        
        Returns:
            Formatted string (e.g., "2 hours 30 minutes")
        """
        hours = minutes // 60
        mins = minutes % 60
        
        if hours > 0:
            return f"{hours} hour{'s' if hours != 1 else ''} {mins} minute{'s' if mins != 1 else ''}"
        else:
            return f"{mins} minute{'s' if mins != 1 else ''}"
    
    def get_attendance_summary(self, duration: int, status: str) -> dict:
        """
        Get detailed attendance summary
        
        Args:
            duration: Duration in minutes
            status: Attendance status
        
        Returns:
            Dictionary with attendance details
        """
        return {
            'duration_minutes': duration,
            'duration_formatted': self.format_duration(duration),
            'status': status,
            'minimum_required': self.minimum_duration,
            'minimum_required_formatted': self.format_duration(self.minimum_duration),
            'is_present': status == "PRESENT",
            'shortage': max(0, self.minimum_duration - duration) if status == "ABSENT" else 0
        }
