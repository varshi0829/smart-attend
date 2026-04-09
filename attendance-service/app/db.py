
import os
import psycopg2
from psycopg2 import pool
from .config import logger

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
        return None
    finally:
        put_connection(conn)

def get_students():
    """Returns {roll_number: name}, {roll_number: section}"""
    rows = execute_query("SELECT roll_number, name, section FROM students")
    if not rows:
        return None, None
    names = {r[0].strip().upper(): r[1] for r in rows}
    sections = {r[0].strip().upper(): r[2] for r in rows}
    return names, sections

def get_teacher_by_name(name):
    """Normalized name lookup"""
    rows = execute_query("SELECT teacher_id, name, department, role FROM teachers WHERE LOWER(name) = LOWER(%s) OR name = %s", (name, name))
    if rows:
        return {"id": rows[0][0], "name": rows[0][1], "department": rows[0][2], "role": rows[0][3]}
    return None

def get_teacher_assignments(teacher_id):
    rows = execute_query("SELECT department, year, section, subject, course_code, class_type FROM faculty_class_assignments WHERE teacher_id = %s", (teacher_id,))
    if not rows:
        return []
    return [{"department": r[0], "year": r[1], "section": r[2], "subject": r[3], "course_code": r[4], "class_type": r[5]} for r in rows]

def get_all_assignments():
    """HOD/Principal view"""
    rows = execute_query("SELECT t.name, t.department as t_dept, a.department, a.year, a.section, a.subject, a.course_code, a.class_type FROM faculty_class_assignments a JOIN teachers t ON a.teacher_id = t.teacher_id")
    if not rows:
        return []
    return [{"teacher_name": r[0], "teacher_dept": r[1], "department": r[2], "year": r[3], "section": r[4], "subject": r[5], "course_code": r[6], "class_type": r[7]} for r in rows]

def save_attendance(roll_number, session_id, timestamp, confidence):
    return execute_query(
        "INSERT INTO attendance (roll_number, session_id, timestamp, confidence) VALUES (%s, %s, %s, %s)",
        (roll_number.upper(), session_id, timestamp, confidence),
        fetch=False
    )

def check_duplicate_attendance(roll_number, session_id):
    rows = execute_query("SELECT 1 FROM attendance WHERE roll_number = %s AND session_id = %s", (roll_number.upper(), session_id))
    return len(rows) > 0 if rows else False

def save_session(session_id, teacher_id, department, year, section, subject, start_time, status='active'):
    return execute_query(
        "INSERT INTO sessions (session_id, teacher_id, department, year, section, subject, start_time, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (session_id) DO NOTHING",
        (session_id, teacher_id, department, year, section, subject, start_time, status),
        fetch=False
    )

def get_student_count(department: str, year: int, section: str) -> int:
    """Get student count for a specific department/year/section"""
    rows = execute_query(
        "SELECT COUNT(*) FROM students WHERE department = %s AND year = %s AND section = %s",
        (department, year, section)
    )
    if rows and rows[0]:
        return rows[0][0]
    return 0

def is_db_available():
    try:
        conn = get_connection()
        if conn:
            put_connection(conn)
            return True
    except:
        pass
    return False
