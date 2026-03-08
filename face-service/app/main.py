import os
import time
import traceback
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from .config import MODEL_NAME, logger, EMBEDDINGS_DIR, THRESHOLD
from .utils import process_uploaded_image, get_embedding
from .matcher import load_student_embeddings, verify_face_match
from .responses import standard_response

app = FastAPI(title="SmartAttend Face Verification Service")

# Allow any origin for local network access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return {"status": "ok", "model": MODEL_NAME}
