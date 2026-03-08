import os
import pickle
import numpy as np
from .config import EMBEDDINGS_DIR, THRESHOLD, logger

def load_student_embeddings(roll_number: str):
    """Load and validate student embeddings from .pkl."""
    roll_no = roll_number.upper()
    file_path = os.path.join(EMBEDDINGS_DIR, f"{roll_no}.pkl")
    
    if not os.path.exists(file_path):
        return None, "RECORD_NOT_FOUND", f"No record found for {roll_no}"
    
    try:
        with open(file_path, "rb") as f:
            data = pickle.load(f)
        
        # Normalize various pkl formats
        if isinstance(data, dict):
            raw_list = data.get("embeddings", [data.get("embedding")])
        elif isinstance(data, (list, tuple, np.ndarray)):
            raw_list = data if isinstance(data, list) else [data]
        else:
            raw_list = [data]

        normalized_list = []
        for i, item in enumerate(raw_list):
            if item is None: continue
            try:
                arr = np.array(item, dtype=np.float32)
                if arr.size > 0:
                    normalized_list.append(arr)
                else:
                    logger.debug(f"[MATCHER] Skip empty vector at index {i} for {roll_no}")
            except (ValueError, TypeError) as e:
                logger.debug(f"[MATCHER] Skip malformed vector at index {i} for {roll_no}: {e}")
            
        if not normalized_list:
            return None, "CORRUPT_EMBEDDING_FILE", "Embedding file exists but contains no valid vectors."

        return normalized_list, None, None
    except Exception as e:
        logger.error(f"[MATCHER] Critical load failure for {roll_no}: {e}")
        return None, "CORRUPT_EMBEDDING_FILE", f"Failed to parse embedding file: {str(e)}"

def verify_face_match(live_embedding, stored_embeddings):
    """
    Comparison logic for identity-first verification.
    Returns: (is_match, best_score, error_code, all_scores, stored_shapes)
    """
    if live_embedding is None or not stored_embeddings:
        return False, 0.0, "INPUT_ERROR", [], []

    norm_live = np.linalg.norm(live_embedding)
    if norm_live < 1e-6 or np.isnan(norm_live):
        return False, 0.0, "INVALID_LIVE_CAPTURE", [], []

    live_shape = list(live_embedding.shape)
    all_scores = []
    stored_shapes = []
    best_score = -1.0
    valid_comparison_count = 0

    for stored_emb in stored_embeddings:
        s_shape = list(stored_emb.shape)
        stored_shapes.append(s_shape)
        
        if s_shape != live_shape:
            all_scores.append(None)
            continue

        norm_stored = np.linalg.norm(stored_emb)
        if norm_stored < 1e-6 or np.isnan(norm_stored):
            all_scores.append(0.0)
            continue
            
        similarity = float(np.dot(live_embedding, stored_emb) / (norm_live * norm_stored))
        if np.isnan(similarity):
            all_scores.append(0.0)
            continue

        all_scores.append(round(similarity, 4))
        valid_comparison_count += 1
        if similarity > best_score:
            best_score = similarity

    if valid_comparison_count == 0:
        return False, 0.0, "NO_VALID_COMPARABLE_EMBEDDINGS", all_scores, stored_shapes

    is_match = best_score >= THRESHOLD
    error_code = None if is_match else "FACE_MISMATCH"
    
    logger.info(f"[MATCHER] Best: {best_score:.4f} | Threshold: {THRESHOLD} | Match: {is_match}")
    return is_match, best_score, error_code, all_scores, stored_shapes
