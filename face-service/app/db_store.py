"""
db_store.py
===========
PostgreSQL + pgvector storage for face embeddings.

Design contract:
  • Every public method returns a result OR None/empty on ANY error.
  • Exceptions are logged and swallowed; callers MUST fallback to .pkl.
  • The DB is OPTIONAL — if DB_ENABLED=false (or DB is down) the rest of the
    service continues using .pkl files without degradation.

Table schema (created by setup_postgres.sh):
    student_face_embeddings(
        id          SERIAL PRIMARY KEY,
        roll_number TEXT NOT NULL,
        embedding   vector(512) NOT NULL,
        created_at  TIMESTAMPTZ DEFAULT NOW(),
        is_active   BOOLEAN DEFAULT TRUE,
        source      TEXT DEFAULT 'insightface_buffalo_l'
    )
    INDEX: HNSW on (embedding vector_cosine_ops)
    INDEX: btree on (roll_number)
"""

import numpy as np
from .config import DB_ENABLED, DB_DSN, EMBEDDING_DIM, logger

# ── Module-level connection pool ─────────────────────────────────────────────
_pool = None


def _get_pool():
    """Lazy-init a psycopg2 SimpleConnectionPool. Returns None on any error."""
    global _pool
    if _pool is not None:
        return _pool
    if not DB_ENABLED:
        return None
    try:
        from psycopg2 import pool as pg_pool
        p = pg_pool.SimpleConnectionPool(1, 5, dsn=DB_DSN, connect_timeout=5)
        _pool = p
        logger.info("[DB] Connection pool initialised.")
        return _pool
    except Exception as exc:
        logger.warning(f"[DB] Pool creation failed (will use .pkl): {exc}")
        return None


def _get_conn():
    """Borrow a connection from the pool. Returns None on failure."""
    p = _get_pool()
    if p is None:
        return None
    try:
        conn = p.getconn()
        # Register pgvector type on this connection
        try:
            from pgvector.psycopg2 import register_vector
            register_vector(conn)
        except Exception:
            pass  # pgvector type registration is optional; adapters still work
        return conn
    except Exception as exc:
        logger.debug(f"[DB] getconn failed: {exc}")
        return None


def _put_conn(conn, failed: bool = False):
    """Return a connection to the pool."""
    p = _get_pool()
    if p and conn:
        try:
            p.putconn(conn, close=failed)
        except Exception:
            pass


# ── Public API ────────────────────────────────────────────────────────────────

def is_available() -> bool:
    """Return True if the DB pool is up and reachable."""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception:
        _put_conn(conn, failed=True)
        return False
    finally:
        _put_conn(conn)


def load_embeddings(roll_number: str):
    """
    Load all active embeddings for a student.

    Returns:
        list[np.ndarray(512,)]  — one or more embeddings
        None                    — student not found OR any DB error
    """
    conn = _get_conn()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT embedding
                FROM   student_face_embeddings
                WHERE  roll_number = %s
                  AND  is_active   = TRUE
                ORDER  BY created_at DESC
                """,
                (roll_number.upper(),),
            )
            rows = cur.fetchall()

        if not rows:
            return None

        result = []
        for (raw,) in rows:
            arr = np.array(raw, dtype=np.float32)
            if arr.shape == (EMBEDDING_DIM,):
                result.append(arr)

        return result if result else None

    except Exception as exc:
        logger.warning(f"[DB] load_embeddings({roll_number}) failed: {exc}")
        _put_conn(conn, failed=True)
        return None
    finally:
        _put_conn(conn)


def save_embedding(roll_number: str, embedding: np.ndarray, source: str = "insightface_buffalo_l") -> bool:
    """
    Insert a new embedding row for a student.
    Returns True on success, False on any error.
    """
    conn = _get_conn()
    if conn is None:
        return False
    try:
        vec = embedding.astype(np.float32).tolist()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO student_face_embeddings (roll_number, embedding, source)
                VALUES (%s, %s::vector, %s)
                """,
                (roll_number.upper(), str(vec), source),
            )
        conn.commit()
        return True
    except Exception as exc:
        logger.error(f"[DB] save_embedding({roll_number}) failed: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _put_conn(conn, failed=True)
        return False
    finally:
        _put_conn(conn)


def deactivate_embeddings(roll_number: str) -> bool:
    """Mark all existing embeddings for a student as inactive (soft-delete)."""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE student_face_embeddings SET is_active = FALSE WHERE roll_number = %s",
                (roll_number.upper(),),
            )
        conn.commit()
        return True
    except Exception as exc:
        logger.error(f"[DB] deactivate({roll_number}) failed: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _put_conn(conn, failed=True)
        return False
    finally:
        _put_conn(conn)


def find_top_k_similar(query_embedding: np.ndarray, k: int = 5):
    """
    DEBUG / admin tool only — do NOT use for attendance marking.
    Returns top-k closest students by cosine similarity using HNSW index.

    Returns list of {"roll_number": str, "similarity": float}
    or empty list on any error.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        vec = query_embedding.astype(np.float32).tolist()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT roll_number,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM   student_face_embeddings
                WHERE  is_active = TRUE
                ORDER  BY embedding <=> %s::vector
                LIMIT  %s
                """,
                (str(vec), str(vec), k),
            )
            rows = cur.fetchall()
        return [{"roll_number": r, "similarity": round(float(s), 4)} for r, s in rows]
    except Exception as exc:
        logger.warning(f"[DB] find_top_k failed: {exc}")
        _put_conn(conn, failed=True)
        return []
    finally:
        _put_conn(conn)


def init():
    """
    Called at service startup. Tries to build the connection pool.
    Always returns; never raises — DB unavailability is not fatal.
    """
    if not DB_ENABLED:
        logger.info("[DB] DB_ENABLED=false — running in .pkl-only mode.")
        return
    pool = _get_pool()
    if pool:
        logger.info("[DB] pgvector store ready.")
    else:
        logger.warning("[DB] pgvector store unavailable — fallback to .pkl active.")