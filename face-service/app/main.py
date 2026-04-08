import os
import socket
import sys
import time
import traceback
import platform
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .config import MODEL_NAME, logger, EMBEDDINGS_DIR, THRESHOLD, MAX_CONTENT_LENGTH, PRODUCTION_MODE
from .utils import process_uploaded_image, get_embedding
from .matcher import load_student_embeddings, verify_face_match
from .responses import standard_response

app = FastAPI(title="SmartAttend Face Verification Service")
model_warmup_ready = False

# Allow any origin for local network access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _validate_embeddings_dir() -> Path:
    path = Path(EMBEDDINGS_DIR)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise RuntimeError(
            f"Cannot create embeddings directory: {path}. Check permissions."
        ) from exc

    if not os.access(path, os.R_OK):
        raise RuntimeError(f"Embeddings directory is not readable: {path}")
    if not os.access(path, os.W_OK):
        raise RuntimeError(f"Embeddings directory is not writable: {path}")

    pkl_count = len(list(path.glob("*.pkl")))
    logger.info(f"[STARTUP] Embeddings directory ready: {path} (files: {pkl_count})")
    return path

def _warmup_deepface_model() -> None:
    from deepface import DeepFace

    global model_warmup_ready
    logger.info(f"[STARTUP] Warming up DeepFace model: {MODEL_NAME}")
    try:
        DeepFace.build_model(MODEL_NAME)
        model_warmup_ready = True
        logger.info(f"[STARTUP] DeepFace model warmup complete: {MODEL_NAME}")
    except Exception as exc:
        logger.error(f"[STARTUP] DeepFace model warmup failed: {exc}")
        raise RuntimeError("DeepFace model warmup failed") from exc

def _log_runtime_diagnostics() -> None:
    logger.info(
        "[STARTUP] Runtime: python=%s platform=%s",
        sys.version.split(" ")[0],
        platform.platform(),
    )
    try:
        import tensorflow as tf
        logger.info("[STARTUP] TensorFlow version: %s", tf.__version__)
    except Exception as exc:
        logger.warning("[STARTUP] TensorFlow version check failed: %s", exc)
    try:
        import deepface
        logger.info("[STARTUP] DeepFace version: %s", getattr(deepface, "__version__", "unknown"))
    except Exception as exc:
        logger.warning("[STARTUP] DeepFace version check failed: %s", exc)

def _validate_socket_runtime_permissions() -> None:
    probe = None
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except PermissionError as exc:
        raise RuntimeError(
            "Socket creation is blocked by the runtime environment. "
            "This is not an app logic failure; check container/sandbox network permissions."
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"Socket runtime check failed with OS error: {exc}. "
            "Check host network policy and security restrictions."
        ) from exc
    finally:
        if probe is not None:
            probe.close()

@app.on_event("startup")
async def startup_preflight():
    logger.info("[STARTUP] Face service preflight started.")
    try:
        _log_runtime_diagnostics()
        _validate_socket_runtime_permissions()
        _validate_embeddings_dir()
        if os.getenv("FACE_SERVICE_SKIP_MODEL_WARMUP", "0") == "1":
            logger.warning("[STARTUP] Skipping model warmup due to FACE_SERVICE_SKIP_MODEL_WARMUP=1")
        else:
            _warmup_deepface_model()
    except Exception as exc:
        logger.error(f"[STARTUP] Preflight failed: {exc}\n{traceback.format_exc()}")
        raise RuntimeError("Face service startup preflight failed") from exc
    logger.info("[STARTUP] Face service preflight completed successfully.")

@app.post("/verify-face")
async def verify_face(roll_number: str = Form(...), image: UploadFile = File(...)):
    start_time = time.time()
    roll_no = roll_number.strip().upper()

    try:
        # Load Stored
        stored, err_code, err_msg = load_student_embeddings(roll_no)
        if not stored:
            status_code = 404 if err_code == "RECORD_NOT_FOUND" else 400
            return standard_response(False, roll_no, err_msg, error_code=err_code, status_code=status_code)

        # Process Live
        content = await image.read()
        
        # Enforce image size limit
        if len(content) > MAX_CONTENT_LENGTH:
            return standard_response(False, roll_no, f"Image too large (max {MAX_CONTENT_LENGTH//(1024*1024)}MB)", error_code="PAYLOAD_TOO_LARGE", status_code=413)

        img_array = process_uploaded_image(content)
        emb_result = get_embedding(img_array)
        
        if emb_result["status"] != "ok":
            return standard_response(False, roll_no, emb_result["message"], error_code=emb_result["status"].upper())

        # Match
        res = verify_face_match(emb_result["embedding"], stored)
        is_match, best_score, match_error, _, _ = res
        
        proc_time = round(time.time() - start_time, 2)
        return standard_response(is_match, roll_no, 
            "Face verified successfully." if is_match else f"Face mismatch (Best: {best_score:.4f})", 
            confidence=best_score, error_code=match_error, processing_time=proc_time)
            
    except Exception as e:
        logger.error(f"[API] VERIFY Error for {roll_no}: {e}\n{traceback.format_exc()}")
        return standard_response(False, roll_no, f"Internal error: {str(e)}", error_code="SERVER_ERROR", status_code=500)

if not PRODUCTION_MODE:
    @app.get("/debug/student/{roll_number}")
    async def debug_student(roll_number: str):
        """Diagnostic endpoint to inspect stored embeddings."""
        roll_no = roll_number.strip().upper()
        file_path = os.path.join(EMBEDDINGS_DIR, f"{roll_no}.pkl")
        exists = os.path.exists(file_path)
        
        stored, err_code, _ = load_student_embeddings(roll_no)
        
        count = 0
        shapes = []
        if stored:
            count = len(stored)
            shapes = [list(s.shape) for s in stored]
            
        return {
            "roll_number": roll_no,
            "exists": exists,
            "count": count,
            "shapes": shapes,
            "error_code": err_code if not stored else None,
            "file_path": file_path
        }

    @app.post("/verify-face-debug")
    async def verify_face_debug(roll_number: str = Form(...), image: UploadFile = File(...)):
        """Advanced diagnostic endpoint for mismatch debugging."""
        roll_no = roll_number.strip().upper()
        try:
            stored, err_code, err_msg = load_student_embeddings(roll_no)
            if not stored: return {"success": False, "error_code": err_code, "message": err_msg}

            content = await image.read()
            img_array = process_uploaded_image(content)
            emb_result = get_embedding(img_array)
            if emb_result["status"] != "ok": return {"success": False, "error_code": emb_result["status"].upper(), "message": emb_result["message"]}

            res = verify_face_match(emb_result["embedding"], stored)
            is_match, best_score, match_error, all_scores, stored_shapes = res

            return {
                "success": is_match,
                "roll_number": roll_no,
                "error_code": match_error,
                "threshold": THRESHOLD,
                "best_score": round(best_score, 4),
                "live_shape": list(emb_result["embedding"].shape),
                "stored_count": len(stored),
                "stored_shapes": stored_shapes,
                "all_scores": all_scores
            }
        except Exception as e:
            return {"success": False, "error": str(e), "trace": traceback.format_exc()}

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "embeddings_dir": EMBEDDINGS_DIR,
        "model_warmup_ready": model_warmup_ready or os.getenv("FACE_SERVICE_SKIP_MODEL_WARMUP", "0") == "1"
    }
