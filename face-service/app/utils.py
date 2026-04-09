"""
utils.py
========
Image decoding + embedding extraction.

get_embedding() is the only function called from main.py.
It now delegates to face_pipeline.extract_embedding() (InsightFace buffalo_l)
instead of DeepFace, but returns the IDENTICAL dict contract so main.py
requires zero changes.

process_uploaded_image() is unchanged — it's pure OpenCV decode logic.
"""

import cv2
import numpy as np
from .config import logger
from .face_pipeline import extract_embedding


def process_uploaded_image(image_bytes: bytes):
    """Convert raw bytes to BGR OpenCV image array."""
    try:
        if not image_bytes:
            return None
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            logger.error("[UTILS] OpenCV failed to decode image buffer.")
        return img
    except Exception as exc:
        logger.error(f"[UTILS] Image decoding failed: {exc}")
        return None


def get_embedding(img_array) -> dict:
    """
    Extract a face embedding from a BGR image array.

    Returns:
        {"status": "ok"|"no_face"|"multiple_faces"|"decode_error"|"error",
         "embedding": np.ndarray|None,
         "message":   str}

    Delegates to InsightFace buffalo_l pipeline (face_pipeline.py).
    Return format is backward-compatible with the original DeepFace version.
    """
    return extract_embedding(img_array)