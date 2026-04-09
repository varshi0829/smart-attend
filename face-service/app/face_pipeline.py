"""
face_pipeline.py
================
InsightFace buffalo_l pipeline — drop-in replacement for DeepFace.

Single responsibility: given a raw BGR image array, return either:
  {"status": "ok", "embedding": np.ndarray(512,), "message": "..."}
or one of the error dicts (status ∈ no_face | multiple_faces | decode_error | error).

The model is loaded exactly ONCE (singleton) and reused for every request.
Model weights are cached at ~/.insightface/models/buffalo_l/ after first download.
"""

import threading
import numpy as np
from .config import (
    INSIGHTFACE_MODEL, INSIGHTFACE_CTX_ID,
    DET_SIZE, DET_SCORE_THRESHOLD, MIN_FACE_SIZE_PX, logger,
    MODEL_NAME, DETECTOR_BACKEND
)

# ── Singleton state ──────────────────────────────────────────────────────────
_face_app   = None
_init_lock  = threading.Lock()
_init_error = None   # set if model failed to load; prevents retry storms


def _build_face_app():
    """Load InsightFace FaceAnalysis once. Thread-safe."""
    global _face_app, _init_error

    with _init_lock:
        if _face_app is not None:
            return _face_app
        # We don't raise here anymore to allow the fallback path to be tried
        if _init_error is not None:
            return None

        try:
            from insightface.app import FaceAnalysis
            logger.info(f"[PIPELINE] Loading InsightFace model: {INSIGHTFACE_MODEL} (ctx={INSIGHTFACE_CTX_ID})")
            app = FaceAnalysis(
                name=INSIGHTFACE_MODEL,
                providers=["CPUExecutionProvider"] if INSIGHTFACE_CTX_ID == 0 else ["CUDAExecutionProvider", "CPUExecutionProvider"]
            )
            app.prepare(ctx_id=INSIGHTFACE_CTX_ID, det_thresh=DET_SCORE_THRESHOLD, det_size=DET_SIZE)
            _face_app = app
            logger.info(f"[PIPELINE] InsightFace {INSIGHTFACE_MODEL} ready.")
            return _face_app
        except Exception as exc:
            _init_error = str(exc)
            logger.error(f"[PIPELINE] InsightFace model load failed: {exc}")
            return None


def warmup():
    """
    Called once at service startup.
    Downloads model weights (first run) and initialises ONNX runtime.
    Does NOT raise on failure to allow fallback service.
    """
    _build_face_app()


def _extract_embedding_deepface_fallback(img_array: np.ndarray) -> dict:
    """
    Fallback to legacy DeepFace pipeline if InsightFace is unavailable.
    """
    try:
        from deepface import DeepFace
        logger.info(f"[PIPELINE] Attempting DeepFace fallback (model={MODEL_NAME}, detector={DETECTOR_BACKEND})")
        
        objs = DeepFace.represent(
            img_path=img_array,
            model_name=MODEL_NAME,
            detector_backend=DETECTOR_BACKEND,
            enforce_detection=True,
            align=True
        )
        
        if not objs:
            return {"status": "no_face", "embedding": None, "message": "No face detected (fallback)."}
            
        if len(objs) > 1:
            return {"status": "multiple_faces", "embedding": None, "message": "Multiple faces detected (fallback)."}
            
        embedding = np.array(objs[0]["embedding"], dtype=np.float32)
        logger.info(f"[PIPELINE] DeepFace fallback successful. Shape={embedding.shape}")
        return {
            "status": "ok",
            "embedding": embedding,
            "message": "Face embedding generated successfully (fallback)."
        }
    except Exception as exc:
        logger.error(f"[PIPELINE] DeepFace fallback also failed: {exc}")
        return {
            "status": "error",
            "embedding": None,
            "message": f"All face models failed: {exc}"
        }


def extract_embedding(img_array: np.ndarray) -> dict:
    """
    Run SCRFD detection + ArcFace embedding on a BGR image array.
    Falls back to DeepFace if InsightFace fails.
    """
    if img_array is None:
        return {
            "status": "decode_error",
            "embedding": None,
            "message": "Failed to decode image data.",
        }

    try:
        app = _build_face_app()
        if app is None:
            return _extract_embedding_deepface_fallback(img_array)
            
        faces = app.get(img_array)
        
        # ── Face-count gate ──────────────────────────────────────────────────────
        if not faces:
            logger.warning("[PIPELINE] No face detected.")
            return {
                "status": "no_face",
                "embedding": None,
                "message": "No face detected.",
            }

        if len(faces) > 1:
            logger.warning(f"[PIPELINE] Multiple faces detected: {len(faces)}")
            return {
                "status": "multiple_faces",
                "embedding": None,
                "message": "Multiple faces detected. Only one person should be in the frame.",
            }

        face = faces[0]

        # ── Confidence gate ──────────────────────────────────────────────────────
        det_score = float(face.det_score) if hasattr(face, "det_score") else 1.0
        if det_score < DET_SCORE_THRESHOLD:
            logger.warning(f"[PIPELINE] Low detection confidence: {det_score:.3f}")
            return {
                "status": "no_face",
                "embedding": None,
                "message": f"Face detection confidence too low ({det_score:.2f}).",
            }

        # ── Size gate ────────────────────────────────────────────────────────────
        bbox = face.bbox.astype(int)   # [x1, y1, x2, y2]
        face_w = int(bbox[2] - bbox[0])
        face_h = int(bbox[3] - bbox[1])
        if face_w < MIN_FACE_SIZE_PX or face_h < MIN_FACE_SIZE_PX:
            logger.warning(f"[PIPELINE] Face too small: {face_w}×{face_h}px")
            return {
                "status": "no_face",
                "embedding": None,
                "message": f"Face too small ({face_w}×{face_h}px). Move closer to camera.",
            }

        # ── Embedding ────────────────────────────────────────────────────────────
        # normed_embedding is already L2-normalised (cosine sim = dot product)
        embedding = np.array(face.normed_embedding, dtype=np.float32)
        logger.info(
            f"[PIPELINE] Embedding OK — shape={embedding.shape} "
            f"bbox=({face_w}×{face_h}) score={det_score:.3f}"
        )
        return {
            "status": "ok",
            "embedding": embedding,
            "message": "Face embedding generated successfully.",
        }
        
    except Exception as exc:
        logger.warning(f"[PIPELINE] InsightFace processing failed, trying fallback: {exc}")
        return _extract_embedding_deepface_fallback(img_array)