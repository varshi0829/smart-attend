"""
matcher.py
==========
Embedding loading + cosine-similarity matching.

Storage lookup order:
  1. PostgreSQL / pgvector (if DB_ENABLED and reachable)
  2. .pkl file fallback  (always available)

The rest of the service (main.py) calls only two functions:
  load_student_embeddings(roll_number) → (list[np.ndarray]|None, err_code|None, err_msg|None)
  verify_face_match(live_emb, stored_embs) → (is_match, best_score, err_code, all_scores, stored_shapes)

Return signatures are IDENTICAL to the original — no callers need to change.
"""

import os
import pickle
import numpy as np
from .config import EMBEDDINGS_DIR, THRESHOLD, logger
from . import db_store


# ── Internal: load from .pkl ──────────────────────────────────────────────────

def _load_from_pkl(roll_number: str):
    """
    Load embeddings from the legacy .pkl file.
    Returns same 3-tuple as load_student_embeddings().
    """
    roll_no   = roll_number.upper()
    file_path = os.path.join(EMBEDDINGS_DIR, f"{roll_no}.pkl")

    if not os.path.exists(file_path):
        return None, "RECORD_NOT_FOUND", f"No record found for {roll_no}"

    try:
        with open(file_path, "rb") as f:
            data = pickle.load(f)

        # Normalise various pkl formats
        if isinstance(data, dict):
            raw_list = data.get("embeddings", [data.get("embedding")])
        elif isinstance(data, (list, tuple, np.ndarray)):
            raw_list = data if isinstance(data, list) else [data]
        else:
            raw_list = [data]

        normalized = []
        for i, item in enumerate(raw_list):
            if item is None:
                continue
            try:
                arr = np.array(item, dtype=np.float32)
                if arr.size > 0:
                    normalized.append(arr)
            except (ValueError, TypeError) as exc:
                logger.debug(f"[MATCHER] Skip malformed vector #{i} for {roll_no}: {exc}")

        if not normalized:
            return None, "CORRUPT_EMBEDDING_FILE", "Embedding file exists but contains no valid vectors."

        return normalized, None, None

    except Exception as exc:
        logger.error(f"[MATCHER] Critical .pkl load failure for {roll_no}: {exc}")
        return None, "CORRUPT_EMBEDDING_FILE", f"Failed to parse embedding file: {exc}"


# ── Public: load (DB-first, .pkl fallback) ────────────────────────────────────

def load_student_embeddings(roll_number: str):
    """
    Load stored embeddings for identity-first verification.

    Try order:
      1. PostgreSQL (if available)
      2. .pkl file

    Returns:
        (embeddings: list[np.ndarray], error_code: str|None, error_msg: str|None)
    """
    roll_no = roll_number.strip().upper()

    # ── 1. Try DB ─────────────────────────────────────────────────────────────
    try:
        db_embs = db_store.load_embeddings(roll_no)
        if db_embs is not None:
            logger.debug(f"[MATCHER] DB hit for {roll_no} ({len(db_embs)} emb)")
            return db_embs, None, None
    except Exception as exc:
        logger.warning(f"[MATCHER] DB lookup error for {roll_no}, falling back to .pkl: {exc}")

    # ── 2. .pkl fallback ──────────────────────────────────────────────────────
    logger.debug(f"[MATCHER] .pkl lookup for {roll_no}")
    return _load_from_pkl(roll_no)


# ── Public: cosine similarity matching ───────────────────────────────────────

def verify_face_match(live_embedding, stored_embeddings):
    """
    Identity-first cosine similarity comparison.

    Compares live_embedding against ALL stored embeddings for the same student
    and takes the best (max) score.

    Returns:
        (is_match: bool,
         best_score: float,
         error_code: str|None,
         all_scores: list,
         stored_shapes: list)
    """
    if live_embedding is None or not stored_embeddings:
        return False, 0.0, "INPUT_ERROR", [], []

    # Validate live embedding
    norm_live = np.linalg.norm(live_embedding)
    if norm_live < 1e-6 or np.isnan(norm_live):
        return False, 0.0, "INVALID_LIVE_CAPTURE", [], []

    live_shape = list(live_embedding.shape)
    # Ensure unit-norm for cosine-as-dot-product
    live_unit  = live_embedding / norm_live

    all_scores   = []
    stored_shapes = []
    best_score   = -1.0
    valid_count  = 0

    for stored_emb in stored_embeddings:
        s_shape = list(stored_emb.shape)
        stored_shapes.append(s_shape)

        if s_shape != live_shape:
            # Shape mismatch — likely old vs new model; skip gracefully
            all_scores.append(None)
            logger.debug(f"[MATCHER] Shape mismatch: live={live_shape} stored={s_shape}")
            continue

        norm_stored = np.linalg.norm(stored_emb)
        if norm_stored < 1e-6 or np.isnan(norm_stored):
            all_scores.append(0.0)
            continue

        stored_unit = stored_emb / norm_stored
        similarity  = float(np.dot(live_unit, stored_unit))

        if np.isnan(similarity):
            all_scores.append(0.0)
            continue

        all_scores.append(round(similarity, 4))
        valid_count += 1
        if similarity > best_score:
            best_score = similarity

    if valid_count == 0:
        return False, 0.0, "NO_VALID_COMPARABLE_EMBEDDINGS", all_scores, stored_shapes

    is_match   = best_score >= THRESHOLD
    error_code = None if is_match else "FACE_MISMATCH"

    logger.info(
        f"[MATCHER] Best={best_score:.4f} | Threshold={THRESHOLD} | Match={is_match} "
        f"| Compared={valid_count}/{len(stored_embeddings)}"
    )
    return is_match, best_score, error_code, all_scores, stored_shapes