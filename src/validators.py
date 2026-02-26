"""Input validation helpers for API and service layers."""

import base64
import binascii
import re
from datetime import datetime
from typing import Optional, Tuple

from . import config


class ValidationError(ValueError):
    """Raised when input validation fails."""


_STUDENT_ID_RE = re.compile(
    rf"^{re.escape(config.STUDENT_ID_PREFIX)}[A-Za-z0-9]+_[A-Za-z0-9_-]+$"
)
_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 ._-]*$")
_ROLL_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_STATUS_VALUES = {"PRESENT", "ABSENT"}
_SUBJECT_VALUES = set(config.SUBJECT_OPTIONS)
_CAMERA_RUN_MODES = {
    config.CAMERA_RUN_MODE_ONCE,
    config.CAMERA_RUN_MODE_SESSION,
    config.CAMERA_RUN_MODE_INTERVAL,
}


def validate_student_id(student_id: str) -> str:
    value = (student_id or "").strip()
    if not value:
        raise ValidationError("student_id is required")
    if len(value) > config.MAX_STUDENT_ID_LENGTH:
        raise ValidationError("student_id is too long")
    if "/" in value or "\\" in value or ".." in value:
        raise ValidationError("student_id contains invalid path characters")
    if not _STUDENT_ID_RE.match(value):
        raise ValidationError(
            f"student_id must follow format {config.STUDENT_ID_PREFIX}RollNumber_Name"
        )
    return value


def validate_name(name: str) -> str:
    value = (name or "").strip()
    if not value:
        raise ValidationError("name is required")
    if len(value) > config.MAX_NAME_LENGTH:
        raise ValidationError("name is too long")
    if not _NAME_RE.match(value):
        raise ValidationError("name contains invalid characters")
    return value


def validate_roll_number(roll_number: str) -> str:
    """
    Validate and auto-format roll number.
    Automatically cleans input by removing common prefixes, separators, and normalizing.
    
    Examples:
        "roll-2301105473" -> "2301105473"
        "Student ID: 2301105473" -> "2301105473"
        "23-01105-473" -> "2301105473"
        "2301 105 473" -> "2301105473"
    """
    value = (roll_number or "").strip()
    if not value:
        raise ValidationError("roll_number is required")
    
    # Convert to uppercase for consistent processing
    value = value.upper()
    
    # Remove separators FIRST to handle cases like "ROLL-NO-123" -> "ROLLNO123", then we remove "ROLLNO"
    value = re.sub(r'[\s\-_/.,:\(\)\[\]]+', '', value)
    
    # Remove common prefix keywords (now that separators are gone)
    # Order matters: Remove compound prefixes first, then simple ones
    prefixes = [
        'ROLLNUMBER', 'ROLLNO',
        'STUDENTNUMBER', 'STUDENTID', 'STUDENTNO', 'STUDENT',
        'REGISTRATIONNO', 'REGISTRATION',
        'REGNUMBER', 'REGNO', 'REG',
        'IDNUMBER', 'IDNO', 'ID',
        'ROLL', 'NUMBER', 'NO',
    ]
    
    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix):]
            break  # Remove only first matching prefix
    
    # Remove any remaining non-alphanumeric characters
    value = re.sub(r'[^A-Z0-9]', '', value)
    
    # Final validation
    if not value:
        raise ValidationError("roll_number is empty after removing special characters")
    if len(value) > config.MAX_ROLL_LENGTH:
        raise ValidationError(f"roll_number is too long (max {config.MAX_ROLL_LENGTH} characters, got {len(value)})")
    
    return value


def validate_status(status: str) -> str:
    value = (status or "").strip().upper()
    if value not in _STATUS_VALUES:
        raise ValidationError("status must be PRESENT or ABSENT")
    return value


def validate_subject(
    subject: Optional[str],
    field_name: str = "subject",
    allow_empty: bool = False,
) -> Optional[str]:
    if subject in (None, ""):
        if allow_empty:
            return None
        raise ValidationError(f"{field_name} is required")

    value = str(subject).strip()
    if value not in _SUBJECT_VALUES:
        allowed = ", ".join(config.SUBJECT_OPTIONS)
        raise ValidationError(f"{field_name} must be one of: {allowed}")
    return value


def validate_camera_run_mode(mode: Optional[str]) -> str:
    value = (mode or "").strip().lower()
    if value not in _CAMERA_RUN_MODES:
        raise ValidationError(
            "camera_run_mode must be one of: once, session, interval"
        )
    return value


def validate_date(date_value: Optional[str], field_name: str = "date") -> Optional[str]:
    if date_value in (None, ""):
        return None
    value = date_value.strip()
    try:
        datetime.strptime(value, config.REPORT_DATE_FORMAT)
    except ValueError as exc:
        raise ValidationError(f"{field_name} must be in YYYY-MM-DD format") from exc
    return value


def parse_limit_offset(limit: Optional[object], offset: Optional[object]) -> Tuple[int, int]:
    parsed_limit = config.DEFAULT_PAGE_LIMIT
    parsed_offset = 0

    if limit not in (None, ""):
        try:
            parsed_limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValidationError("limit must be an integer") from exc
    if offset not in (None, ""):
        try:
            parsed_offset = int(offset)
        except (TypeError, ValueError) as exc:
            raise ValidationError("offset must be an integer") from exc

    if parsed_limit < 1:
        raise ValidationError("limit must be >= 1")
    if parsed_limit > config.MAX_PAGE_LIMIT:
        raise ValidationError(f"limit must be <= {config.MAX_PAGE_LIMIT}")
    if parsed_offset < 0:
        raise ValidationError("offset must be >= 0")

    return parsed_limit, parsed_offset


def validate_base64_image(image_payload: str) -> bytes:
    if not image_payload:
        raise ValidationError("image is required")

    encoded = image_payload.split(",", 1)[1] if "," in image_payload else image_payload
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValidationError("invalid base64 image payload") from exc

    if not image_bytes:
        raise ValidationError("image payload is empty")
    if len(image_bytes) > config.MAX_IMAGE_BYTES:
        raise ValidationError(
            f"image payload is too large (max {config.MAX_IMAGE_BYTES} bytes)"
        )
    return image_bytes
