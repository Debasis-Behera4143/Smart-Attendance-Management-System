"""Database manager for attendance, logs, settings, and analytics."""



import logging

import os

import sqlite3

from datetime import datetime, timedelta

from typing import Dict, List, Optional, Tuple



from . import config





logger = logging.getLogger(__name__)



TABLE_DEFINITIONS = (

    "CREATE TABLE IF NOT EXISTS students (student_id TEXT PRIMARY KEY, name TEXT NOT NULL, roll_number TEXT UNIQUE NOT NULL, registered_date TEXT NOT NULL)",

    "CREATE TABLE IF NOT EXISTS entry_log (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, name TEXT NOT NULL, entry_time TEXT NOT NULL, date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'INSIDE', FOREIGN KEY (student_id) REFERENCES students(student_id))",

    "CREATE TABLE IF NOT EXISTS exit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, name TEXT NOT NULL, entry_id INTEGER NOT NULL, exit_time TEXT NOT NULL, date TEXT NOT NULL, FOREIGN KEY (student_id) REFERENCES students(student_id), FOREIGN KEY (entry_id) REFERENCES entry_log(id))",

    "CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, name TEXT NOT NULL, entry_time TEXT NOT NULL, exit_time TEXT NOT NULL, duration INTEGER NOT NULL CHECK(duration >= 0), status TEXT NOT NULL CHECK(status IN ('PRESENT', 'ABSENT')), date TEXT NOT NULL, subject TEXT NOT NULL DEFAULT 'Operating System', FOREIGN KEY (student_id) REFERENCES students(student_id))",

    "CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)",

)



INDEX_DEFINITIONS = (

    "CREATE INDEX IF NOT EXISTS idx_entry_log_student_date_status ON entry_log (student_id, date, status)",

    "CREATE INDEX IF NOT EXISTS idx_entry_log_entry_time ON entry_log (entry_time DESC)",

    "CREATE UNIQUE INDEX IF NOT EXISTS idx_entry_unique_inside_per_subject ON entry_log (student_id, date, subject) WHERE status = 'INSIDE'",

    "CREATE INDEX IF NOT EXISTS idx_exit_log_date ON exit_log (date DESC)",

    "CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance (date DESC)",

    "CREATE INDEX IF NOT EXISTS idx_attendance_student_date ON attendance (student_id, date DESC)",

    "CREATE INDEX IF NOT EXISTS idx_attendance_subject_date ON attendance (subject, date DESC)",

    "CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_unique_session ON attendance (student_id, date, entry_time)",

)



ATTENDANCE_INSERT_SQL = (

    "INSERT INTO attendance (student_id, name, entry_time, exit_time, duration, status, date, subject) "

    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"

)



ATTENDANCE_UPSERT_SQL = (

    "INSERT INTO attendance (student_id, name, entry_time, exit_time, duration, status, date, subject) "

    "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(student_id, date, entry_time) DO UPDATE SET "

    "name = excluded.name, exit_time = excluded.exit_time, duration = excluded.duration, "

    "status = excluded.status, subject = excluded.subject"

)





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

        conn = sqlite3.connect(self.db_path, timeout=config.DB_TIMEOUT, check_same_thread=False)



        conn.execute("PRAGMA journal_mode = WAL")



        conn.execute("PRAGMA busy_timeout = 30000")



        conn.execute("PRAGMA synchronous = NORMAL")

        conn.execute("PRAGMA cache_size = -64000")

        conn.execute("PRAGMA temp_store = MEMORY")

        conn.execute("PRAGMA foreign_keys = ON")

        return _SQLiteConnectionContext(conn)



    @staticmethod

    def _fetch_open_entry(

        cursor: sqlite3.Cursor,

        student_id: str,

        date: str,

        subject: Optional[str] = None,

    ) -> Optional[Tuple[int, str, str, str]]:

        if subject:

            cursor.execute(

                """
                SELECT id, entry_time, date, subject FROM entry_log
                WHERE student_id = ? AND date = ? AND subject = ? AND status = 'INSIDE'
                ORDER BY id DESC LIMIT 1
                """,

                (student_id, date, subject),

            )

        else:

            cursor.execute(

                """
                SELECT id, entry_time, date, subject FROM entry_log
                WHERE student_id = ? AND date = ? AND status = 'INSIDE'
                ORDER BY id DESC LIMIT 1
                """,

                (student_id, date),

            )

        return cursor.fetchone()



    @staticmethod

    def _fetch_stale_entries(

        cursor: sqlite3.Cursor,

        cutoff_time: str,

        student_id: Optional[str] = None,

    ) -> List[Tuple]:

        if student_id:

            cursor.execute(

                """
                SELECT id, student_id, name, entry_time, date
                FROM entry_log
                WHERE student_id = ? AND status = 'INSIDE' AND entry_time < ?
                ORDER BY entry_time DESC
                """,

                (student_id, cutoff_time),

            )

        else:

            cursor.execute(

                """
                SELECT id, student_id, name, entry_time, date
                FROM entry_log
                WHERE status = 'INSIDE' AND entry_time < ?
                ORDER BY entry_time DESC
                """,

                (cutoff_time,),

            )

        return cursor.fetchall()



    @staticmethod

    def _attendance_params(

        student_id: str,

        name: str,

        entry_time: str,

        exit_time: str,

        duration: int,

        status: str,

        date: str,

        subject: str,

    ) -> Tuple[object, ...]:

        return (

            student_id,

            name,

            entry_time,

            exit_time,

            duration,

            status,

            date,

            subject,

        )



    def _save_attendance_record(

        self,

        student_id: str,

        name: str,

        entry_time: str,

        exit_time: str,

        duration: int,

        status: str,

        date: str,

        subject: str,

        upsert: bool = False,

    ) -> bool:

        sql = ATTENDANCE_UPSERT_SQL if upsert else ATTENDANCE_INSERT_SQL

        params = self._attendance_params(

            student_id,

            name,

            entry_time,

            exit_time,

            duration,

            status,

            date,

            subject,

        )

        try:

            with self.get_connection() as conn:

                conn.cursor().execute(sql, params)

            return True

        except sqlite3.IntegrityError:

            if upsert:

                logger.exception("Error upserting attendance")

            else:

                logger.info(

                    "Skipping duplicate attendance insert for student_id=%s entry_time=%s",

                    student_id,

                    entry_time,

                )

            return False

        except Exception:

            logger.exception("Error upserting attendance" if upsert else "Error saving attendance")

            return False



    def _find_entry_for_exit(

        self,

        cursor: sqlite3.Cursor,

        student_id: str,

        name: str,

        current_date: str,

        subject: str,

    ) -> Optional[Tuple[int, str, str, str]]:



        entry_record = self._fetch_open_entry(cursor, student_id, current_date, subject)

        if entry_record:

            return entry_record





        entry_record = self._fetch_open_entry(cursor, student_id, current_date)

        if entry_record:

            logger.info(

                "Manual exit: Found entry with different subject for %s (%s)",

                name,

                student_id,

            )

            return entry_record





        yesterday = (datetime.now() - timedelta(days=1)).strftime(config.REPORT_DATE_FORMAT)

        entry_record = self._fetch_open_entry(cursor, student_id, yesterday)

        if entry_record:

            logger.warning(

                "Cross-midnight exit detected: %s (%s) entered on %s, exiting on %s",

                name,

                student_id,

                yesterday,

                current_date,

            )

        return entry_record



    def _get_attendance_rows(

        self,

        where_sql: str = "",

        params: Tuple[object, ...] = (),

        order_by: str = "date DESC, entry_time DESC",

        limit: Optional[int] = None,

    ) -> List[Tuple]:

        query = f"""
            SELECT student_id, name, entry_time, exit_time, duration, status, date, subject
            FROM attendance
            {where_sql}
            ORDER BY {order_by}
        """

        query_params: List[object] = list(params)

        if limit is not None:

            query = f"{query}\n            LIMIT ?"

            query_params.append(limit)



        with self.get_connection() as conn:

            cursor = conn.cursor()

            cursor.execute(query, tuple(query_params))

            return cursor.fetchall()



    def create_tables(self):

        with self.get_connection() as conn:

            cursor = conn.cursor()

            for statement in TABLE_DEFINITIONS:

                cursor.execute(statement)



            self._ensure_attendance_schema(cursor)

            self._create_indexes(cursor)

            self._ensure_default_settings(cursor)



    def _create_indexes(self, cursor):

        for statement in INDEX_DEFINITIONS:

            cursor.execute(statement)



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



        default_subject = config.DEFAULT_SUBJECT.replace("'", "''")



        cursor.execute("PRAGMA table_info(attendance)")

        columns = [row[1] for row in cursor.fetchall()]

        if "subject" not in columns:

            cursor.execute(

                f"""
                ALTER TABLE attendance
                ADD COLUMN subject TEXT NOT NULL DEFAULT '{default_subject}'
                """

            )





        cursor.execute("PRAGMA table_info(entry_log)")

        entry_columns = [row[1] for row in cursor.fetchall()]

        if "subject" not in entry_columns:

            cursor.execute(

                f"""
                ALTER TABLE entry_log
                ADD COLUMN subject TEXT NOT NULL DEFAULT '{default_subject}'
                """

            )

            logger.info("Added 'subject' column to entry_log table")





            cursor.execute("DROP INDEX IF EXISTS idx_entry_unique_inside_per_day")

            logger.info("Dropped old unique constraint on entry_log")



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



    def get_stale_entries(self, student_id: Optional[str] = None, max_age_hours: int = 24) -> List[Dict]:

        """
        Find entries that are still marked 'INSIDE' but are older than max_age_hours.
        These are likely forgotten exits or system errors.
        """

        now = datetime.now()

        cutoff_time = (now - timedelta(hours=max_age_hours)).strftime(config.REPORT_DATETIME_FORMAT)



        with self.get_connection() as conn:

            rows = self._fetch_stale_entries(conn.cursor(), cutoff_time, student_id)

            return [

                {

                    "id": row[0],

                    "student_id": row[1],

                    "name": row[2],

                    "entry_time": row[3],

                    "date": row[4],

                    "age_hours": round(

                        (now - datetime.strptime(row[3], config.REPORT_DATETIME_FORMAT)).total_seconds()

                        / 3600,

                        1,

                    ),

                }

                for row in rows

            ]



    def auto_cleanup_stale_entries(self, max_age_hours: int = 24, mark_as_absent: bool = True) -> int:

        """
        Automatically cleanup stale entries (older than max_age_hours).
        Returns count of entries cleaned.
        """

        with self.get_connection() as conn:

            cursor = conn.cursor()

            cutoff_time = (datetime.now() - timedelta(hours=max_age_hours)).strftime(config.REPORT_DATETIME_FORMAT)

            current_time = datetime.now().strftime(config.REPORT_DATETIME_FORMAT)



            stale_entries = self._fetch_stale_entries(cursor, cutoff_time)

            if not stale_entries:

                return 0



            cleaned_count = 0

            for entry_id, student_id, name, entry_time, entry_date in stale_entries:

                cursor.execute(

                    "UPDATE entry_log SET status = 'AUTO_CLEANUP' WHERE id = ?",

                    (entry_id,),

                )

                cursor.execute(

                    """
                    INSERT INTO exit_log (student_id, name, entry_id, exit_time, date)
                    VALUES (?, ?, ?, ?, ?)
                    """,

                    (student_id, name, entry_id, current_time, entry_date),

                )

                if mark_as_absent:

                    entry_dt = datetime.strptime(entry_time, config.REPORT_DATETIME_FORMAT)

                    exit_dt = datetime.strptime(current_time, config.REPORT_DATETIME_FORMAT)

                    duration = int((exit_dt - entry_dt).total_seconds() / 60)

                    cursor.execute(

                        """
                        INSERT OR IGNORE INTO attendance (
                            student_id, name, subject, entry_time, exit_time,
                            duration, status, date
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,

                        (

                            student_id,

                            name,

                            "AUTO_CLEANUP",

                            entry_time,

                            current_time,

                            duration,

                            "ABSENT",

                            entry_date,

                        ),

                    )



                cleaned_count += 1

                logger.info(f"Auto-cleanup: {name} ({student_id}) - entry from {entry_time}")



            return cleaned_count



    def mark_entry(self, student_id: str, name: str, subject: Optional[str] = None) -> Optional[Dict[str, object]]:

        """Mark entry and return entry details including actual timestamp used."""

        current_date = datetime.now().strftime(config.REPORT_DATE_FORMAT)

        current_time = datetime.now().strftime(config.REPORT_DATETIME_FORMAT)

        resolved_subject = (subject or "").strip() or config.DEFAULT_SUBJECT



        try:

            with self.get_connection() as conn:

                cursor = conn.cursor()



                if self._fetch_open_entry(cursor, student_id, current_date, resolved_subject):

                    logger.info(f"Entry already exists for {student_id} on {current_date} for {resolved_subject}")

                    return None



                cursor.execute(

                    """
                    INSERT INTO entry_log (student_id, name, entry_time, date, status, subject)
                    VALUES (?, ?, ?, ?, 'INSIDE', ?)
                    """,

                    (student_id, name, current_time, current_date, resolved_subject),

                )

                entry_id = int(cursor.lastrowid)

                logger.info(f"Entry marked: {name} ({student_id}) - subject: {resolved_subject}")

                return {

                    "entry_id": entry_id,

                    "entry_time": current_time,

                    "date": current_date,

                    "subject": resolved_subject,

                }

        except sqlite3.IntegrityError as e:

            logger.warning(f"IntegrityError on entry for {student_id}: {e}")

            return None

        except sqlite3.OperationalError as e:

            logger.error(f"Database locked during entry for {student_id}: {e}")

            return None



    def mark_exit(self, student_id: str, name: str) -> Optional[Tuple[int, str, str]]:

        with self.get_connection() as conn:

            cursor = conn.cursor()

            current_date = datetime.now().strftime(config.REPORT_DATE_FORMAT)

            current_time = datetime.now().strftime(config.REPORT_DATETIME_FORMAT)



            entry_record = self._fetch_open_entry(cursor, student_id, current_date)

            if not entry_record:

                return None



            entry_id, entry_time, _, _ = entry_record



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
        Handles cross-midnight entries (entry yesterday, exit today).
        """

        with self.get_connection() as conn:

            cursor = conn.cursor()

            current_date = datetime.now().strftime(config.REPORT_DATE_FORMAT)

            current_time = datetime.now().strftime(config.REPORT_DATETIME_FORMAT)

            resolved_subject = (subject or "").strip() or config.DEFAULT_SUBJECT

            entry_record = self._find_entry_for_exit(

                cursor,

                student_id,

                name,

                current_date,

                resolved_subject,

            )

            if not entry_record:

                return None



            entry_id, entry_time, _, entry_subject = entry_record





            resolved_subject = entry_subject



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

        return self._save_attendance_record(

            student_id=student_id,

            name=name,

            entry_time=entry_time,

            exit_time=exit_time,

            duration=duration,

            status=status,

            date=date,

            subject=subject,

            upsert=False,

        )



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

        return self._save_attendance_record(

            student_id=student_id,

            name=name,

            entry_time=entry_time,

            exit_time=exit_time,

            duration=duration,

            status=status,

            date=date,

            subject=subject,

            upsert=True,

        )



    def get_attendance_by_date(

        self, date: str, subject: Optional[str] = None

    ) -> List[Tuple]:

        where_sql = "WHERE date = ? AND subject = ?" if subject else "WHERE date = ?"

        params = (date, subject) if subject else (date,)

        return self._get_attendance_rows(

            where_sql=where_sql,

            params=params,

            order_by="entry_time",

        )



    def get_all_attendance(self, subject: Optional[str] = None) -> List[Tuple]:

        where_sql = "WHERE subject = ?" if subject else ""

        params = (subject,) if subject else ()

        return self._get_attendance_rows(where_sql=where_sql, params=params)



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

        where_sql = "WHERE student_id = ? AND subject = ?" if subject else "WHERE student_id = ?"

        params = (student_id, subject) if subject else (student_id,)

        return self._get_attendance_rows(

            where_sql=where_sql,

            params=params,

            order_by="date DESC",

        )



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



    def delete_student(self, student_id: str) -> bool:

        """Delete a student and all associated data (attendance, entry, exit logs)."""

        try:

            with self.get_connection() as conn:

                cursor = conn.cursor()

                for table_name in ("attendance", "exit_log", "entry_log", "students"):

                    cursor.execute(f"DELETE FROM {table_name} WHERE student_id = ?", (student_id,))



                logger.info(f"Successfully deleted student: {student_id}")

                return True

        except Exception as e:

            logger.exception(f"Error deleting student {student_id}: {e}")

            return False



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

        where_sql = "WHERE student_id = ? AND subject = ?" if subject else "WHERE student_id = ?"

        params = (student_id, subject) if subject else (student_id,)

        return self._get_attendance_rows(where_sql=where_sql, params=params, limit=limit)



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

