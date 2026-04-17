
import os
import psycopg2
from psycopg2 import pool
import logging

logger = logging.getLogger("QRService.DB")

DB_DSN = os.getenv("DB_DSN", "postgresql://cse:cse@localhost:5432/smartattend_db")
_pool = None

def get_pool():
    global _pool
    if _pool is None:
        try:
            _pool = psycopg2.pool.SimpleConnectionPool(1, 10, dsn=DB_DSN)
        except Exception as e:
            logger.error(f"PostgreSQL pool init failed: {e}")
    return _pool

def save_session_to_db(session_data):
    p = get_pool()
    if not p: return False
    conn = p.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sessions (session_id, teacher_id, department, year, section, subject, start_time, status)
                VALUES (%s, (SELECT teacher_id FROM teachers WHERE name = %s LIMIT 1), %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id) DO NOTHING
                """,
                (
                    session_data["id"],
                    session_data["instructor_name"],
                    session_data["department"],
                    int(session_data["year"]),
                    session_data["section"],
                    session_data["subject"],
                    session_data["start_time"],
                    session_data["status"]
                )
            )
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to save session to DB: {e}")
        conn.rollback()
        return False
    finally:
        p.putconn(conn)
