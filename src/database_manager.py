"""Database manager for attendance, logs, settings, and analytics."""

import logging
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from . import config


logger = logging.getLogger(__name__)


class _SQLiteConnectionContext:
    """Context manager that commits/rolls back and always closes the connection."""

    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def __enter__(self) -> sqlite3.Connection:
        return self._connection

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        try:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            self._connection.close()
        return False

    def __getattr__(self, item):
        return getattr(self._connection, item)


class DatabaseManager:
    """Centralized database operations for the attendance system."""

    def __init__(self):
        self.db_path = config.DATABASE_FILE
        self._ensure_database_directory()
        self.create_tables()

    def _ensure_database_directory(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=config.DB_TIMEOUT)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return _SQLiteConnectionContext(conn)

    def create_tables(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    roll_number TEXT UNIQUE NOT NULL,
                    registered_date TEXT NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS entry_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    entry_time TEXT NOT NULL,
                    date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'INSIDE',
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS exit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    entry_id INTEGER NOT NULL,
                    exit_time TEXT NOT NULL,
                    date TEXT NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(student_id),
                    FOREIGN KEY (entry_id) REFERENCES entry_log(id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT NOT NULL,
                    duration INTEGER NOT NULL CHECK(duration >= 0),
                    status TEXT NOT NULL CHECK(status IN ('PRESENT', 'ABSENT')),
                    date TEXT NOT NULL,
                    subject TEXT NOT NULL DEFAULT 'Operating System',
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            self._ensure_attendance_schema(cursor)
            self._create_indexes(cursor)
            self._ensure_default_settings(cursor)
            conn.commit()

    def _create_indexes(self, cursor):
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_entry_log_student_date_status
            ON entry_log (student_id, date, status)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_entry_log_entry_time
            ON entry_log (entry_time DESC)
            """
        )
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_entry_unique_inside_per_day
            ON entry_log (student_id, date)
            WHERE status = 'INSIDE'
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_exit_log_date
            ON exit_log (date DESC)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_attendance_date
            ON attendance (date DESC)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_attendance_student_date
            ON attendance (student_id, date DESC)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_attendance_subject_date
            ON attendance (subject, date DESC)
            """
        )
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_unique_session
            ON attendance (student_id, date, entry_time)
            """
        )

    def _ensure_default_settings(self, cursor):
        now = datetime.now().strftime(config.REPORT_DATETIME_FORMAT)
        defaults = {
            "camera_policy": config.DEFAULT_CAMERA_POLICY,
            "camera_run_mode": config.DEFAULT_CAMERA_RUN_MODE,
            "use_yolo": str(config.ENABLE_YOLO_IF_AVAILABLE).lower(),
            "active_subject": config.DEFAULT_SUBJECT,
            "run_interval_seconds": str(config.DEFAULT_RUN_INTERVAL_SECONDS),
            "session_duration_minutes": str(config.DEFAULT_SESSION_DURATION_MINUTES),
            "fair_motion_threshold": str(config.DEFAULT_FAIR_MOTION_THRESHOLD),
        }

        for key, value in defaults.items():
            cursor.execute(
                """
                INSERT OR IGNORE INTO system_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, value, now),
            )

    def _ensure_attendance_schema(self, cursor):
        cursor.execute("PRAGMA table_info(attendance)")
        columns = [row[1] for row in cursor.fetchall()]
        if "subject" not in columns:
            default_subject = config.DEFAULT_SUBJECT.replace("'", "''")
            cursor.execute(
                f"""
                ALTER TABLE attendance
                ADD COLUMN subject TEXT NOT NULL DEFAULT '{default_subject}'
                """
            )

    def register_student(self, student_id: str, name: str, roll_number: str) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                registered_date = datetime.now().strftime(config.REPORT_DATE_FORMAT)
                cursor.execute(
                    """
                    INSERT INTO students (student_id, name, roll_number, registered_date)
                    VALUES (?, ?, ?, ?)
                    """,
                    (student_id, name, roll_number, registered_date),
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_student_info(self, student_id: str) -> Optional[Tuple]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT student_id, name, roll_number, registered_date
                FROM students WHERE student_id = ?
                """,
                (student_id,),
            )
            return cursor.fetchone()

    def mark_entry(self, student_id: str, name: str) -> Optional[int]:
        current_date = datetime.now().strftime(config.REPORT_DATE_FORMAT)
        current_time = datetime.now().strftime(config.REPORT_DATETIME_FORMAT)

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO entry_log (student_id, name, entry_time, date, status)
                    VALUES (?, ?, ?, ?, 'INSIDE')
                    """,
                    (student_id, name, current_time, current_date),
                )
                conn.commit()
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError:
            return None

    def mark_exit(self, student_id: str, name: str) -> Optional[Tuple[int, str, str]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            current_date = datetime.now().strftime(config.REPORT_DATE_FORMAT)
            current_time = datetime.now().strftime(config.REPORT_DATETIME_FORMAT)

            cursor.execute(
                """
                SELECT id, entry_time FROM entry_log
                WHERE student_id = ? AND date = ? AND status = 'INSIDE'
                ORDER BY id DESC LIMIT 1
                """,
                (student_id, current_date),
            )
            entry_record = cursor.fetchone()
            if not entry_record:
                return None

            entry_id, entry_time = entry_record

            cursor.execute(
                "UPDATE entry_log SET status = 'EXITED' WHERE id = ?",
                (entry_id,),
            )
            cursor.execute(
                """
                INSERT INTO exit_log (student_id, name, entry_id, exit_time, date)
                VALUES (?, ?, ?, ?, ?)
                """,
                (student_id, name, entry_id, current_time, current_date),
            )
            conn.commit()

            return (entry_id, entry_time, current_time)

    def mark_exit_and_save_attendance(
        self,
        student_id: str,
        name: str,
        minimum_duration: int,
        subject: Optional[str] = None,
    ) -> Optional[Dict[str, object]]:
        """
        Atomically process exit and attendance creation in one transaction.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            current_date = datetime.now().strftime(config.REPORT_DATE_FORMAT)
            current_time = datetime.now().strftime(config.REPORT_DATETIME_FORMAT)

            cursor.execute(
                """
                SELECT id, entry_time FROM entry_log
                WHERE student_id = ? AND date = ? AND status = 'INSIDE'
                ORDER BY id DESC LIMIT 1
                """,
                (student_id, current_date),
            )
            entry_record = cursor.fetchone()
            if not entry_record:
                return None

            entry_id, entry_time = entry_record
            entry_dt = datetime.strptime(entry_time, config.REPORT_DATETIME_FORMAT)
            exit_dt = datetime.strptime(current_time, config.REPORT_DATETIME_FORMAT)
            if exit_dt < entry_dt:
                logger.warning(
                    "Skipping exit for %s due to invalid times (entry=%s, exit=%s)",
                    student_id,
                    entry_time,
                    current_time,
                )
                return None

            duration = int((exit_dt - entry_dt).total_seconds() / 60)
            status = "PRESENT" if duration >= minimum_duration else "ABSENT"
            date = entry_time.split()[0]
            resolved_subject = (subject or "").strip() or config.DEFAULT_SUBJECT

            cursor.execute(
                "UPDATE entry_log SET status = 'EXITED' WHERE id = ?",
                (entry_id,),
            )
            cursor.execute(
                """
                INSERT INTO exit_log (student_id, name, entry_id, exit_time, date)
                VALUES (?, ?, ?, ?, ?)
                """,
                (student_id, name, entry_id, current_time, current_date),
            )
            cursor.execute(
                """
                INSERT INTO attendance (
                    student_id, name, entry_time, exit_time, duration, status, date, subject
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    name,
                    entry_time,
                    current_time,
                    duration,
                    status,
                    date,
                    resolved_subject,
                ),
            )
            conn.commit()

            return {
                "entry_id": entry_id,
                "entry_time": entry_time,
                "exit_time": current_time,
                "duration": duration,
                "status": status,
                "date": date,
                "subject": resolved_subject,
            }

    def save_attendance(
        self,
        student_id: str,
        name: str,
        entry_time: str,
        exit_time: str,
        duration: int,
        status: str,
        date: str,
        subject: str = config.DEFAULT_SUBJECT,
    ) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO attendance (
                        student_id, name, entry_time, exit_time, duration, status, date, subject
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        student_id,
                        name,
                        entry_time,
                        exit_time,
                        duration,
                        status,
                        date,
                        subject,
                    ),
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            logger.info(
                "Skipping duplicate attendance insert for student_id=%s entry_time=%s",
                student_id,
                entry_time,
            )
            return False
        except Exception:
            logger.exception("Error saving attendance")
            return False

    def upsert_attendance(
        self,
        student_id: str,
        name: str,
        entry_time: str,
        exit_time: str,
        duration: int,
        status: str,
        date: str,
        subject: str = config.DEFAULT_SUBJECT,
    ) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO attendance (
                        student_id, name, entry_time, exit_time, duration, status, date, subject
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(student_id, date, entry_time) DO UPDATE SET
                        name = excluded.name,
                        exit_time = excluded.exit_time,
                        duration = excluded.duration,
                        status = excluded.status,
                        subject = excluded.subject
                    """,
                    (
                        student_id,
                        name,
                        entry_time,
                        exit_time,
                        duration,
                        status,
                        date,
                        subject,
                    ),
                )
                conn.commit()
            return True
        except Exception:
            logger.exception("Error upserting attendance")
            return False

    def get_attendance_by_date(
        self, date: str, subject: Optional[str] = None
    ) -> List[Tuple]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if subject:
                cursor.execute(
                    """
                    SELECT student_id, name, entry_time, exit_time, duration, status, date, subject
                    FROM attendance
                    WHERE date = ? AND subject = ?
                    ORDER BY entry_time
                    """,
                    (date, subject),
                )
            else:
                cursor.execute(
                    """
                    SELECT student_id, name, entry_time, exit_time, duration, status, date, subject
                    FROM attendance
                    WHERE date = ?
                    ORDER BY entry_time
                    """,
                    (date,),
                )
            return cursor.fetchall()

    def get_all_attendance(self, subject: Optional[str] = None) -> List[Tuple]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if subject:
                cursor.execute(
                    """
                    SELECT student_id, name, entry_time, exit_time, duration, status, date, subject
                    FROM attendance
                    WHERE subject = ?
                    ORDER BY date DESC, entry_time DESC
                    """,
                    (subject,),
                )
            else:
                cursor.execute(
                    """
                    SELECT student_id, name, entry_time, exit_time, duration, status, date, subject
                    FROM attendance
                    ORDER BY date DESC, entry_time DESC
                    """
                )
            return cursor.fetchall()

    def get_attendance_filtered(
        self,
        date: Optional[str] = None,
        student_id: Optional[str] = None,
        status: Optional[str] = None,
        subject: Optional[str] = None,
        limit: int = config.DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> Tuple[List[Tuple], int]:
        conditions: List[str] = []
        params: List[object] = []

        if date:
            conditions.append("date = ?")
            params.append(date)
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if subject:
            conditions.append("subject = ?")
            params.append(subject)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT COUNT(1)
                FROM attendance
                {where_clause}
                """,
                tuple(params),
            )
            total = int(cursor.fetchone()[0])

            paged_params = params + [limit, offset]
            cursor.execute(
                f"""
                SELECT student_id, name, entry_time, exit_time, duration, status, date, subject
                FROM attendance
                {where_clause}
                ORDER BY date DESC, entry_time DESC
                LIMIT ? OFFSET ?
                """,
                tuple(paged_params),
            )
            rows = cursor.fetchall()

        return rows, total

    def get_student_attendance(
        self, student_id: str, subject: Optional[str] = None
    ) -> List[Tuple]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if subject:
                cursor.execute(
                    """
                    SELECT student_id, name, entry_time, exit_time, duration, status, date, subject
                    FROM attendance
                    WHERE student_id = ? AND subject = ?
                    ORDER BY date DESC
                    """,
                    (student_id, subject),
                )
            else:
                cursor.execute(
                    """
                    SELECT student_id, name, entry_time, exit_time, duration, status, date, subject
                    FROM attendance
                    WHERE student_id = ?
                    ORDER BY date DESC
                    """,
                    (student_id,),
                )
            return cursor.fetchall()

    def get_all_students(self) -> List[Tuple]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT student_id, name, roll_number, registered_date
                FROM students
                ORDER BY student_id
                """
            )
            return cursor.fetchall()

    def get_recent_entries(self, limit: int = config.MAX_RECENT_ITEMS) -> List[Tuple]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT student_id, name, entry_time, status
                FROM entry_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return cursor.fetchall()

    def get_recent_exits(self, limit: int = config.MAX_RECENT_ITEMS) -> List[Tuple]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT student_id, name, entry_time, exit_time, duration, status, date, subject
                FROM attendance
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return cursor.fetchall()

    def get_student_subject_summary(self, student_id: str) -> List[Dict[str, object]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    subject,
                    COUNT(1) as total_classes,
                    SUM(CASE WHEN status = 'PRESENT' THEN 1 ELSE 0 END) as present_classes,
                    SUM(CASE WHEN status = 'ABSENT' THEN 1 ELSE 0 END) as absent_classes,
                    AVG(duration) as avg_duration
                FROM attendance
                WHERE student_id = ?
                GROUP BY subject
                ORDER BY subject
                """,
                (student_id,),
            )
            rows = cursor.fetchall()

        summary: List[Dict[str, object]] = []
        for subject, total, present, absent, avg_duration in rows:
            total_val = int(total or 0)
            present_val = int(present or 0)
            absent_val = int(absent or 0)
            attendance_rate = round((present_val / total_val) * 100, 2) if total_val else 0.0
            summary.append(
                {
                    "subject": subject,
                    "total_classes": total_val,
                    "present_classes": present_val,
                    "absent_classes": absent_val,
                    "attendance_rate": attendance_rate,
                    "average_duration_minutes": round(float(avg_duration), 2)
                    if avg_duration
                    else 0.0,
                }
            )

        return summary

    def get_student_subject_records(
        self,
        student_id: str,
        subject: Optional[str] = None,
        limit: int = 100,
    ) -> List[Tuple]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if subject:
                cursor.execute(
                    """
                    SELECT student_id, name, entry_time, exit_time, duration, status, date, subject
                    FROM attendance
                    WHERE student_id = ? AND subject = ?
                    ORDER BY date DESC, entry_time DESC
                    LIMIT ?
                    """,
                    (student_id, subject, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT student_id, name, entry_time, exit_time, duration, status, date, subject
                    FROM attendance
                    WHERE student_id = ?
                    ORDER BY date DESC, entry_time DESC
                    LIMIT ?
                    """,
                    (student_id, limit),
                )
            return cursor.fetchall()

    def get_inside_students(self, limit: int = config.MAX_RECENT_ITEMS) -> List[Tuple]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT student_id, name, entry_time, date
                FROM entry_log
                WHERE status = 'INSIDE'
                ORDER BY entry_time DESC
                LIMIT ?
                """,
                (limit,),
            )
            return cursor.fetchall()

    def get_analytics(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> Dict[str, object]:
        conditions: List[str] = []
        params: List[object] = []

        if from_date:
            conditions.append("date >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("date <= ?")
            params.append(to_date)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT
                    COUNT(1),
                    SUM(CASE WHEN status = 'PRESENT' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status = 'ABSENT' THEN 1 ELSE 0 END),
                    AVG(duration),
                    MIN(duration),
                    MAX(duration)
                FROM attendance
                {where_clause}
                """,
                tuple(params),
            )
            row = cursor.fetchone() or (0, 0, 0, None, None, None)
            total, present, absent, avg_duration, min_duration, max_duration = row

            cursor.execute(
                f"""
                SELECT date, COUNT(1) as count
                FROM attendance
                {where_clause}
                GROUP BY date
                ORDER BY date DESC
                LIMIT 30
                """,
                tuple(params),
            )
            by_date = [{"date": r[0], "count": r[1]} for r in cursor.fetchall()]

            cursor.execute(
                f"""
                SELECT student_id, name, COUNT(1) as present_days
                FROM attendance
                WHERE status = 'PRESENT'
                {"AND date >= ?" if from_date else ""}
                {"AND date <= ?" if to_date else ""}
                GROUP BY student_id, name
                ORDER BY present_days DESC, student_id ASC
                LIMIT 5
                """,
                tuple(params),
            )
            top_students = [
                {"student_id": r[0], "name": r[1], "present_days": r[2]}
                for r in cursor.fetchall()
            ]

        total = int(total or 0)
        present = int(present or 0)
        absent = int(absent or 0)
        attendance_rate = round((present / total) * 100, 2) if total else 0.0

        return {
            "total_records": total,
            "present": present,
            "absent": absent,
            "attendance_rate": attendance_rate,
            "average_duration_minutes": round(float(avg_duration), 2) if avg_duration else 0,
            "min_duration_minutes": int(min_duration or 0),
            "max_duration_minutes": int(max_duration or 0),
            "trend_last_30_days": by_date,
            "top_students": top_students,
        }

    def set_setting(self, key: str, value: str) -> bool:
        now = datetime.now().strftime(config.REPORT_DATETIME_FORMAT)
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO system_settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (key, value, now),
                )
                conn.commit()
            return True
        except Exception:
            logger.exception("Error updating setting %s", key)
            return False

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM system_settings WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()
            if not row:
                return default
            return row[0]

    def get_system_settings(self) -> Dict[str, str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM system_settings")
            rows = cursor.fetchall()
            return {key: value for key, value in rows}
