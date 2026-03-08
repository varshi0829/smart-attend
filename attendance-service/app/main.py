from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import httpx
import time
import logging
import os
from datetime import datetime, timezone
from .responses import standard_response
from .integrations import verify_face, verify_qr
from .storage import db
from .config import FACE_SERVICE_URL, QR_SERVICE_URL, ENABLE_DAILY_LIMIT, ATTENDANCE_TIMEZONE, SERVICE_TIMEOUT, LOG_LEVEL

app = FastAPI(title="SmartAttend Attendance Orchestrator")

# Allow any origin for local network access (development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("Orchestrator")

async def get_service_status(url: str):
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(f"{url}/health", timeout=2.0)
            return {
                "status": "UP" if res.status_code == 200 else "DOWN", 
                "details": res.json() if res.status_code == 200 else None
            }
        except Exception as e:
            return {"status": "DOWN", "error": str(e)}

@app.get("/debug/pipeline")
async def debug_pipeline():
    qr_status = await get_service_status(QR_SERVICE_URL)
    face_status = await get_service_status(FACE_SERVICE_URL)
    
    last = db.get_last_attempt()
    student_debug = None
    
    if last and last.get("roll_number"):
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    f"{FACE_SERVICE_URL}/debug/student/{last['roll_number']}", 
                    timeout=SERVICE_TIMEOUT
                )
                if res.status_code == 200:
                    student_debug = res.json()
        except Exception:
            student_debug = {"error": "Face service debug endpoint unreachable."}

    return {
        "services": {
            "qr_service": qr_status,
            "face_service": face_status
        },
        "config": {
            "enable_daily_limit": ENABLE_DAILY_LIMIT,
            "timezone": ATTENDANCE_TIMEZONE
        },
        "student_embedding_status": student_debug,
        "last_attempt": last,
        "total_records": db.get_total_records()
    }

@app.post("/attendance/mark")
async def mark_attendance(
    roll_number: str = Form(...),
    qr_token: str = Form(...),
    image: UploadFile = File(...)
):
    start_time = time.time()
    roll_no = roll_number.strip().upper()
    qr_tkn = qr_token.strip()
    
    if not roll_no or not qr_tkn:
        return standard_response(False, "Roll number and QR token are required.", error_code="INVALID_INPUT", status_code=400)
    
    image_bytes = await image.read()
    if not image_bytes:
        return standard_response(False, "Image file is empty.", error_code="INVALID_INPUT", status_code=400)

    # QR Verification
    logger.info(f"[PIPELINE] Starting QR verification for roll={roll_no}, token_len={len(qr_tkn)}")
    qr_res, qr_status = await verify_qr(roll_no, qr_tkn)
    if qr_status != 200 or not qr_res.get("success"):
        error_code = qr_res.get("error_code", "QR_VALIDATION_FAILED")
        msg = qr_res.get("message", "QR validation failed")
        logger.warning(f"[PIPELINE] QR verification FAILED: error_code={error_code}, msg={msg}")
        db.set_last_attempt(roll_no, "FAILED_QR", {"error_code": error_code, "msg": msg})
        return standard_response(False, msg, error_code=error_code, status_code=qr_status if qr_status < 500 else 503)

    # Face Verification
    face_res, face_status = await verify_face(roll_no, image_bytes, image.filename)
    if face_status != 200 or not face_res.get("success"):
        error_code = face_res.get("error_code", "FACE_VERIFICATION_FAILED")
        msg = face_res.get("message", "Face verification failed")
        db.set_last_attempt(roll_no, "FAILED_FACE", {"error_code": error_code, "msg": msg})
        return standard_response(False, msg, error_code=error_code, status_code=face_status if face_status < 500 else 503)

    qr_data = qr_res.get("data", {})
    session_id = qr_data.get("session_id")
    instructor_id = qr_data.get("instructor_id", "UNKNOWN")

    if not session_id:
        return standard_response(
            False,
            "Invalid session info.",
            error_code="INTEGRATION_ERROR",
            status_code=502
        )

    # Atomic Save
    record, error = db.mark_attendance_atomic(
        roll_no, 
        session_id, 
        instructor_id, 
        face_res.get("confidence", 0.0),
        enable_daily_limit=ENABLE_DAILY_LIMIT
    )

    if error:
        db.set_last_attempt(roll_no, "DENIED", {"error_code": error})
        msg = "Attendance already marked for this session." if error == "DUPLICATE_ATTENDANCE" else "Attendance already marked for today."
        return standard_response(False, msg, error_code=error, status_code=400)

    proc_time = round(time.time() - start_time, 2)
    db.set_last_attempt(roll_no, "SUCCESS", {"attendance_id": record["attendance_id"]})
    return standard_response(True, "Attendance marked successfully.", data=record, processing_time=proc_time)

@app.get("/attendance/session/{session_id}")
async def get_session_history(session_id: str):
    records = db.get_by_session(session_id)
    enriched = []
    for r in records:
        ts = r.get("timestamp", "")
        dt = None
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                pass
        date_str = dt.strftime("%Y-%m-%d") if dt else ""
        time_str = dt.strftime("%H:%M:%S") if dt else ""
        enriched.append({
            "roll_number": r.get("roll_number"),
            "name": get_student_name(r.get("roll_number", "")),
            "date": date_str,
            "time": time_str
        })
    return standard_response(True, f"Found {len(enriched)} records", data=enriched)

def get_student_name(roll_number: str) -> str:
    """Look up student name from CSV. Returns 'Unknown Student' if not found."""
    import csv
    roll = roll_number.strip().upper()
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "backend", "students.csv")
    if not os.path.exists(csv_path):
        return "Unknown Student"
    try:
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("rollnumber", "").strip().upper() == roll:
                    return row.get("name", "Unknown Student").strip()
    except Exception:
        pass
    return "Unknown Student"

@app.get("/health")
async def health():
    return {"status": "ok"}
