
import os
import psycopg2
import psycopg2.errorcodes
from psycopg2 import pool
from datetime import datetime, timezone
from .config import logger

# Printed once when a privilege error is detected so the operator knows what to run.
_OWNERSHIP_FIX_SQL = """\
  Run the following as a PostgreSQL superuser (e.g. postgres) to fix ownership:
    ALTER TABLE sessions                OWNER TO cse;
    ALTER TABLE attendance              OWNER TO cse;
    ALTER TABLE students                OWNER TO cse;
    ALTER TABLE teachers                OWNER TO cse;
    ALTER TABLE faculty_class_assignments OWNER TO cse;
  Then restart the attendance service.
"""
_ownership_warning_shown = False

# Configuration
DB_DSN = os.getenv("DB_DSN", "postgresql://cse:cse@localhost:5432/smartattend_db")
DB_POOL_MIN = 1
DB_POOL_MAX = 10

_pool = None

def get_pool():
    global _pool
    if _pool is None:
        try:
            _pool = psycopg2.pool.SimpleConnectionPool(DB_POOL_MIN, DB_POOL_MAX, dsn=DB_DSN)
            logger.info("Connected to PostgreSQL successfully.")
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            return None
    return _pool

def get_connection():
    p = get_pool()
    if p:
        return p.getconn()
    return None

def put_connection(conn):
    p = get_pool()
    if p and conn:
        p.putconn(conn)

def execute_query(query, params=None, fetch=True):
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if fetch:
                return cur.fetchall()
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        put_connection(conn)

def is_db_available():
    try:
        conn = get_connection()
        if conn:
            put_connection(conn)
            return True
    except Exception:
        pass
    return False

# ─────────────────────────────────────────────────────────────────────────────
# MIGRATIONS — safe to run on every startup
# ─────────────────────────────────────────────────────────────────────────────

def run_migrations():
    """
    Ensure all required tables and columns exist.
    CREATE TABLE IF NOT EXISTS handles fresh DBs.
    ALTER TABLE ADD COLUMN IF NOT EXISTS handles existing DBs missing new cols.
    Safe to run on every startup.
    """
    if not is_db_available():
        logger.warning("[MIGRATION] DB not available, skipping migrations.")
        return

    # Step 1: Create tables with full schema (no-op if they already exist)
    execute_query("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id    TEXT PRIMARY KEY,
            teacher_id    TEXT,
            teacher_name  TEXT,
            teacher_email TEXT,
            department    TEXT,
            year          TEXT,
            section       TEXT,
            subject       TEXT,
            semester      TEXT,
            start_time    TIMESTAMPTZ,
            ended_at      TIMESTAMPTZ,
            status        TEXT DEFAULT 'active',
            present_count INTEGER DEFAULT 0,
            total_count   INTEGER DEFAULT 0,
            absent_count  INTEGER DEFAULT 0,
            mail_sent     BOOLEAN DEFAULT FALSE,
            mail_sent_at  TIMESTAMPTZ
        )
    """, fetch=False)

    execute_query("""
        CREATE TABLE IF NOT EXISTS attendance (
            id           SERIAL PRIMARY KEY,
            roll_number  TEXT NOT NULL,
            session_id   TEXT NOT NULL,
            student_name TEXT,
            timestamp    TIMESTAMPTZ,
            confidence   FLOAT
        )
    """, fetch=False)

    execute_query("""
        CREATE TABLE IF NOT EXISTS teachers (
            teacher_id TEXT PRIMARY KEY,
            name       TEXT,
            department TEXT,
            role       TEXT DEFAULT 'teacher'
        )
    """, fetch=False)

    execute_query("""
        CREATE TABLE IF NOT EXISTS students (
            roll_number TEXT PRIMARY KEY,
            name        TEXT,
            section     TEXT,
            department  TEXT,
            year        INTEGER
        )
    """, fetch=False)

    execute_query("""
        CREATE TABLE IF NOT EXISTS faculty_class_assignments (
            id          SERIAL PRIMARY KEY,
            teacher_id  TEXT,
            department  TEXT,
            year        TEXT,
            section     TEXT,
            subject     TEXT,
            course_code TEXT,
            class_type  TEXT
        )
    """, fetch=False)

    # Step 2: ADD COLUMN IF NOT EXISTS for existing tables.
    # Tables created by a different DB user (e.g. postgres) cannot be ALTER-ed by
    # the app user (cse) — pgcode 42501 (insufficient_privilege).
    # On privilege failure we log the exact SQL needed and continue gracefully;
    # the app still works (file-based fallback) while the operator fixes ownership.
    migration_alters = [
        ("ALTER TABLE sessions    ADD COLUMN IF NOT EXISTS teacher_name  TEXT",        "sessions.teacher_name"),
        ("ALTER TABLE sessions    ADD COLUMN IF NOT EXISTS teacher_email TEXT",        "sessions.teacher_email"),
        ("ALTER TABLE sessions    ADD COLUMN IF NOT EXISTS semester      TEXT",        "sessions.semester"),
        ("ALTER TABLE sessions    ADD COLUMN IF NOT EXISTS ended_at      TIMESTAMPTZ","sessions.ended_at"),
        ("ALTER TABLE sessions    ADD COLUMN IF NOT EXISTS present_count INTEGER DEFAULT 0", "sessions.present_count"),
        ("ALTER TABLE sessions    ADD COLUMN IF NOT EXISTS total_count   INTEGER DEFAULT 0", "sessions.total_count"),
        ("ALTER TABLE sessions    ADD COLUMN IF NOT EXISTS absent_count  INTEGER DEFAULT 0", "sessions.absent_count"),
        ("ALTER TABLE sessions    ADD COLUMN IF NOT EXISTS mail_sent     BOOLEAN DEFAULT FALSE", "sessions.mail_sent"),
        ("ALTER TABLE sessions    ADD COLUMN IF NOT EXISTS mail_sent_at  TIMESTAMPTZ","sessions.mail_sent_at"),
        ("ALTER TABLE attendance  ADD COLUMN IF NOT EXISTS student_name  TEXT",        "attendance.student_name"),
        ("ALTER TABLE students    ADD COLUMN IF NOT EXISTS department    TEXT",        "students.department"),
        ("ALTER TABLE students    ADD COLUMN IF NOT EXISTS year          INTEGER",     "students.year"),
    ]
    for sql, description in migration_alters:
        _run_migration_alter(sql, description)

    logger.info("[MIGRATION] DB migrations complete.")


def _run_migration_alter(sql: str, description: str):
    """
    Execute a single ALTER TABLE migration statement.
    Handles ownership errors (pgcode 42501) with a clear operator hint.
    All other errors are logged but non-fatal — migrations never crash the service.
    """
    global _ownership_warning_shown
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    except psycopg2.Error as e:
        try:
            conn.rollback()
        except Exception:
            pass
        if e.pgcode == psycopg2.errorcodes.INSUFFICIENT_PRIVILEGE:
            if not _ownership_warning_shown:
                _ownership_warning_shown = True
                logger.warning(
                    "[MIGRATION] Ownership error — app user lacks ALTER permission.\n"
                    + _OWNERSHIP_FIX_SQL
                )
            logger.warning(f"[MIGRATION] Skipped (privilege): {description}")
        else:
            logger.error(f"[MIGRATION] Failed ({e.pgcode}): {description} — {e}")
    finally:
        put_connection(conn)


# ─────────────────────────────────────────────────────────────────────────────
# STUDENT QUERIES
# ─────────────────────────────────────────────────────────────────────────────

def get_students():
    """Returns {roll_number: name}, {roll_number: section}"""
    rows = execute_query("SELECT roll_number, name, section FROM students")
    if not rows:
        return None, None
    names    = {r[0].strip().upper(): r[1] for r in rows}
    sections = {r[0].strip().upper(): r[2] for r in rows}
    return names, sections

def get_student_count(department: str, year: int, section: str) -> int:
    """Get student count for a specific department/year/section."""
    rows = execute_query(
        "SELECT COUNT(*) FROM students WHERE department = %s AND year = %s AND section = %s",
        (department, year, section)
    )
    if rows and rows[0]:
        return rows[0][0]
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# TEACHER / ASSIGNMENT QUERIES
# ─────────────────────────────────────────────────────────────────────────────

def get_teacher_by_name(name):
    """Normalized name lookup."""
    rows = execute_query(
        "SELECT teacher_id, name, department, role FROM teachers WHERE LOWER(name) = LOWER(%s) OR name = %s",
        (name, name)
    )
    if rows:
        return {"id": rows[0][0], "name": rows[0][1], "department": rows[0][2], "role": rows[0][3]}
    return None

def get_teacher_assignments(teacher_id):
    rows = execute_query(
        "SELECT department, year, section, subject, course_code, class_type FROM faculty_class_assignments WHERE teacher_id = %s",
        (teacher_id,)
    )
    if not rows:
        return []
    return [
        {"department": r[0], "year": r[1], "section": r[2], "subject": r[3], "course_code": r[4], "class_type": r[5]}
        for r in rows
    ]

def get_all_assignments():
    """HOD/Principal view."""
    rows = execute_query(
        """SELECT t.name, t.department as t_dept, a.department, a.year, a.section, a.subject, a.course_code, a.class_type
           FROM faculty_class_assignments a JOIN teachers t ON a.teacher_id = t.teacher_id"""
    )
    if not rows:
        return []
    return [
        {"teacher_name": r[0], "teacher_dept": r[1], "department": r[2], "year": r[3],
         "section": r[4], "subject": r[5], "course_code": r[6], "class_type": r[7]}
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# SESSION QUERIES
# ─────────────────────────────────────────────────────────────────────────────

def save_session(session_id, teacher_id, department, year, section, subject, start_time, status='active'):
    """Original minimal save — kept for backward compatibility (not called in main flow)."""
    return execute_query(
        """INSERT INTO sessions (session_id, teacher_id, department, year, section, subject, start_time, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (session_id) DO NOTHING""",
        (session_id, teacher_id, department, year, section, subject, start_time, status),
        fetch=False
    )

def save_session_full(session_id, teacher_id, teacher_name, department, year, section, subject, start_time):
    """
    Upsert a session row with full data.
    Called from finalize_session_in_db() so the session row exists before finalization.
    """
    return execute_query(
        """INSERT INTO sessions
               (session_id, teacher_id, teacher_name, department, year, section, subject, start_time, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')
           ON CONFLICT (session_id) DO UPDATE SET
               teacher_name = EXCLUDED.teacher_name,
               status       = sessions.status""",   # don't overwrite 'ended' if already finalized
        (session_id, teacher_id, teacher_name, department, year, section, subject, start_time),
        fetch=False
    )

def finalize_session(session_id, teacher_name, ended_at, present_count, total_count, absent_count,
                     teacher_email=None, semester=None):
    """
    Update session row with end-of-session summary.
    Called after session ends and report is generated.
    teacher_email: Phase 5 will populate from real faculty data — leave None for now.
    semester:      Phase 5 may populate from assignment data — leave None for now.
    """
    return execute_query(
        """UPDATE sessions SET
               teacher_name  = COALESCE(%s, teacher_name),
               teacher_email = %s,
               semester      = %s,
               ended_at      = %s,
               present_count = %s,
               total_count   = %s,
               absent_count  = %s,
               status        = 'ended'
           WHERE session_id = %s""",
        (teacher_name, teacher_email, semester, ended_at, present_count, total_count, absent_count, session_id),
        fetch=False
    )

def get_ended_sessions(instructor_id, dept, year, section):
    """
    Return ended sessions for a specific instructor+class, newest first.
    Used for the Reports / History view in the instructor app.
    """
    rows = execute_query(
        """SELECT session_id, teacher_id, teacher_name, department, year, section, subject,
                  start_time, ended_at, present_count, total_count, absent_count,
                  mail_sent, mail_sent_at, semester
           FROM sessions
           WHERE teacher_id  = %s
             AND department  = %s
             AND year        = %s
             AND section     = %s
             AND status      = 'ended'
           ORDER BY start_time DESC""",
        (instructor_id, dept, year, section)
    )
    if not rows:
        return []
    return [
        {
            "session_id":   r[0],
            "teacher_id":   r[1],
            "teacher_name": r[2],
            "department":   r[3],
            "year":         r[4],
            "section":      r[5],
            "subject":      r[6],
            "start_time":   r[7].isoformat() if r[7] else None,
            "ended_at":     r[8].isoformat() if r[8] else None,
            "present_count": r[9]  or 0,
            "total_count":   r[10] or 0,
            "absent_count":  r[11] or 0,
            "mail_sent":     bool(r[12]),
            "mail_sent_at":  r[13].isoformat() if r[13] else None,
            "semester":      r[14],
        }
        for r in rows
    ]

def get_session_by_id_from_db(session_id):
    """
    Fetch a single session row by session_id.
    Used in Phase 2 send-mail endpoint.
    """
    rows = execute_query(
        """SELECT session_id, teacher_id, teacher_name, teacher_email, department, year, section,
                  subject, semester, start_time, ended_at, present_count, total_count, absent_count,
                  mail_sent, mail_sent_at, status
           FROM sessions WHERE session_id = %s""",
        (session_id,)
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "session_id":    r[0],
        "teacher_id":    r[1],
        "teacher_name":  r[2],
        "teacher_email": r[3],
        "department":    r[4],
        "year":          r[5],
        "section":       r[6],
        "subject":       r[7],
        "semester":      r[8],
        "start_time":    r[9].isoformat()  if r[9]  else None,
        "ended_at":      r[10].isoformat() if r[10] else None,
        "present_count": r[11] or 0,
        "total_count":   r[12] or 0,
        "absent_count":  r[13] or 0,
        "mail_sent":     bool(r[14]),
        "mail_sent_at":  r[15].isoformat() if r[15] else None,
        "status":        r[16],
    }

def mark_mail_sent(session_id):
    """
    Mark a session as having had its attendance email sent.
    Called from Phase 2 send-mail endpoint after successful delivery.
    """
    return execute_query(
        "UPDATE sessions SET mail_sent = TRUE, mail_sent_at = %s WHERE session_id = %s",
        (datetime.now(timezone.utc).isoformat(), session_id),
        fetch=False
    )


# ─────────────────────────────────────────────────────────────────────────────
# ATTENDANCE QUERIES
# ─────────────────────────────────────────────────────────────────────────────

def save_attendance(roll_number, session_id, timestamp, confidence):
    """Save an attendance record. student_name is updated later by update_attendance_student_names."""
    return execute_query(
        "INSERT INTO attendance (roll_number, session_id, timestamp, confidence) VALUES (%s, %s, %s, %s)",
        (roll_number.upper(), session_id, timestamp, confidence),
        fetch=False
    )

def check_duplicate_attendance(roll_number, session_id):
    rows = execute_query(
        "SELECT 1 FROM attendance WHERE roll_number = %s AND session_id = %s",
        (roll_number.upper(), session_id)
    )
    return len(rows) > 0 if rows else False

def update_attendance_student_names(session_id, roll_name_map):
    """
    Bulk-update student_name for all attendance records in a session.
    Called from finalize_session_in_db() after names dict is available.
    roll_name_map: {roll_number: student_name}
    """
    for roll, name in roll_name_map.items():
        execute_query(
            "UPDATE attendance SET student_name = %s WHERE roll_number = %s AND session_id = %s",
            (name, roll.strip().upper(), session_id),
            fetch=False
        )

def get_attendance_by_session_from_db(session_id):
    """
    Return all attendance records for a session from DB, ordered by time.
    Used by reports/list and send-mail endpoints.
    """
    rows = execute_query(
        """SELECT roll_number, student_name, timestamp, confidence
           FROM attendance
           WHERE session_id = %s
           ORDER BY timestamp""",
        (session_id,)
    )
    if not rows:
        return []
    return [
        {
            "roll_number": r[0],
            "name":        r[1] or "Unknown",
            "timestamp":   r[2].isoformat() if r[2] else None,
            "confidence":  r[3],
        }
        for r in rows
    ]
