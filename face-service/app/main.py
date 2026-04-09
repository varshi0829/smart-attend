import os
import socket
import sys
import time
import traceback
import platform
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from .config import logger, EMBEDDINGS_DIR, THRESHOLD, MAX_CONTENT_LENGTH, PRODUCTION_MODE, INSIGHTFACE_MODEL, DB_ENABLED
from .utils import process_uploaded_image, get_embedding
from .matcher import load_student_embeddings, verify_face_match
from .responses import standard_response
from . import db_store
from . import face_pipeline

app = FastAPI(title="SmartAttend Face Verification Service")

# ── CORS (unchanged) ──────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup helpers ───────────────────────────────────────────────────────────

def _validate_embeddings_dir() -> Path:
    path = Path(EMBEDDINGS_DIR)
    path.mkdir(parents=True, exist_ok=True)
    if not os.access(path, os.R_OK):
        raise RuntimeError(f"Embeddings directory not readable: {path}")
    if not os.access(path, os.W_OK):
        raise RuntimeError(f"Embeddings directory not writable: {path}")
    pkl_count = len(list(path.glob("*.pkl")))
    logger.info(f"[STARTUP] Embeddings directory: {path}  (.pkl files: {pkl_count})")
    return path


def _log_runtime_diagnostics() -> None:
    logger.info(
        "[STARTUP] Runtime: python=%s  platform=%s",
        sys.version.split(" ")[0],
        platform.platform(),
    )
    try:
        import insightface
        logger.info("[STARTUP] InsightFace version: %s", insightface.__version__)
    except Exception as exc:
        logger.warning("[STARTUP] InsightFace version check failed: %s", exc)
    try:
        import onnxruntime
        logger.info("[STARTUP] ONNXRuntime version: %s", onnxruntime.__version__)
    except Exception as exc:
        logger.warning("[STARTUP] ONNXRuntime version check failed: %s", exc)


def _validate_socket_runtime_permissions() -> None:
    probe = None
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except (PermissionError, OSError) as exc:
        raise RuntimeError(f"Socket runtime check failed: {exc}") from exc
    finally:
        if probe is not None:
            probe.close()


def _warmup_insightface_model() -> None:
    if os.getenv("FACE_SERVICE_SKIP_MODEL_WARMUP", "0") == "1":
        logger.warning("[STARTUP] Skipping model warmup (FACE_SERVICE_SKIP_MODEL_WARMUP=1)")
        return
    logger.info(f"[STARTUP] Warming up InsightFace model: {INSIGHTFACE_MODEL}")
    face_pipeline.warmup()
    
    if face_pipeline._face_app is not None:
        logger.info("[STARTUP] InsightFace loaded successfully.")
    else:
        logger.error("[STARTUP] InsightFace model load FAILED. Fallback to DeepFace is active.")
    
    # Always log that fallback is available as a safety net
    logger.info("[STARTUP] Legacy fallback pipeline (DeepFace) is available.")


@app.on_event("startup")
async def startup_preflight():
    logger.info("[STARTUP] Face service preflight started.")
    try:
        _log_runtime_diagnostics()
        _validate_socket_runtime_permissions()
        _validate_embeddings_dir()
        db_store.init()            # non-fatal — DB unavailability is OK
        _warmup_insightface_model() # now non-fatal too
    except Exception as exc:
        # We only catch critical system errors here (dir permissions, etc.)
        logger.error(f"[STARTUP] CRITICAL Preflight failed: {exc}\n{traceback.format_exc()}")
        raise RuntimeError("Face service startup preflight failed") from exc
    logger.info("[STARTUP] Face service preflight completed successfully.")


# ── Primary endpoint (UNCHANGED contract) ────────────────────────────────────

@app.post("/verify-face")
async def verify_face(roll_number: str = Form(...), image: UploadFile = File(...)):
    start_time = time.time()
    roll_no = roll_number.strip().upper()

    try:
        # 1. Load stored embeddings (DB → .pkl)
        stored, err_code, err_msg = load_student_embeddings(roll_no)
        if not stored:
            status_code = 404 if err_code == "RECORD_NOT_FOUND" else 400
            return standard_response(False, roll_no, err_msg, error_code=err_code, status_code=status_code)

        # 2. Decode and size-check incoming image
        content = await image.read()
        if len(content) > MAX_CONTENT_LENGTH:
            return standard_response(
                False, roll_no,
                f"Image too large (max {MAX_CONTENT_LENGTH // (1024*1024)} MB)",
                error_code="PAYLOAD_TOO_LARGE", status_code=413
            )

        img_array = process_uploaded_image(content)

        # 3. Extract live embedding (InsightFace)
        emb_result = get_embedding(img_array)
        if emb_result["status"] != "ok":
            return standard_response(
                False, roll_no,
                emb_result["message"],
                error_code=emb_result["status"].upper()
            )

        # 4. Cosine similarity match
        is_match, best_score, match_error, _, _ = verify_face_match(emb_result["embedding"], stored)

        proc_time = round(time.time() - start_time, 2)
        return standard_response(
            is_match, roll_no,
            "Face verified successfully." if is_match else f"Face mismatch (Best: {best_score:.4f})",
            confidence=best_score,
            error_code=match_error,
            processing_time=proc_time,
        )

    except Exception as exc:
        logger.error(f"[API] VERIFY Error for {roll_no}: {exc}\n{traceback.format_exc()}")
        return standard_response(False, roll_no, f"Internal error: {exc}", error_code="SERVER_ERROR", status_code=500)


# ── Health (UNCHANGED contract, updated model name) ───────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": INSIGHTFACE_MODEL,
        "embeddings_dir": EMBEDDINGS_DIR,
        "model_warmup_ready": face_pipeline._face_app is not None
            or os.getenv("FACE_SERVICE_SKIP_MODEL_WARMUP", "0") == "1",
        "db_enabled": DB_ENABLED,
        "db_available": db_store.is_available(),
        "threshold": THRESHOLD,
    }


# ── Debug endpoints (unchanged; production-gated) ────────────────────────────

if not PRODUCTION_MODE:
    @app.get("/debug/student/{roll_number}")
    async def debug_student(roll_number: str):
        """Diagnostic endpoint to inspect stored embeddings."""
        roll_no   = roll_number.strip().upper()
        pkl_path  = os.path.join(EMBEDDINGS_DIR, f"{roll_no}.pkl")
        stored, err_code, _ = load_student_embeddings(roll_no)
        count  = len(stored) if stored else 0
        shapes = [list(s.shape) for s in stored] if stored else []
        return {
            "roll_number":  roll_no,
            "pkl_exists":   os.path.exists(pkl_path),
            "db_enabled":   DB_ENABLED,
            "db_available": db_store.is_available(),
            "count":        count,
            "shapes":       shapes,
            "error_code":   err_code if not stored else None,
        }

    @app.post("/verify-face-debug")
    async def verify_face_debug(roll_number: str = Form(...), image: UploadFile = File(...)):
        """Advanced diagnostic for mismatch debugging."""
        roll_no = roll_number.strip().upper()
        try:
            stored, err_code, err_msg = load_student_embeddings(roll_no)
            if not stored:
                return {"success": False, "error_code": err_code, "message": err_msg}

            content   = await image.read()
            img_array = process_uploaded_image(content)
            emb_result = get_embedding(img_array)
            if emb_result["status"] != "ok":
                return {"success": False, "error_code": emb_result["status"].upper(), "message": emb_result["message"]}

            is_match, best_score, match_error, all_scores, stored_shapes = verify_face_match(
                emb_result["embedding"], stored
            )
            return {
                "success":        is_match,
                "roll_number":    roll_no,
                "error_code":     match_error,
                "threshold":      THRESHOLD,
                "best_score":     round(best_score, 4),
                "live_shape":     list(emb_result["embedding"].shape),
                "stored_count":   len(stored),
                "stored_shapes":  stored_shapes,
                "all_scores":     all_scores,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc), "trace": traceback.format_exc()}

    @app.get("/debug/top-k/{roll_number}")
    async def debug_top_k(roll_number: str, image: UploadFile = File(...), k: int = 5):
        """
        Admin/debug only: find top-k closest students using pgvector HNSW.
        NOT used for attendance marking.
        """
        if not DB_ENABLED:
            return {"error": "DB_ENABLED=false — this endpoint requires pgvector."}
        roll_no   = roll_number.strip().upper()
        content   = await image.read()
        img_array = process_uploaded_image(content)
        emb_result = get_embedding(img_array)
        if emb_result["status"] != "ok":
            return {"success": False, "error_code": emb_result["status"].upper()}
        results = db_store.find_top_k_similar(emb_result["embedding"], k=k)
        return {"roll_number": roll_no, "top_k": results}