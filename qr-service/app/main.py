import time
import httpx
from fastapi import FastAPI, Query, Body, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import logging
import traceback
from .session_store import store
from .responses import standard_response
from .config import QR_EXPIRY_SECONDS

app = FastAPI(title="SmartAttend QR Session Service")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QRService")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

class SessionStartRequest(BaseModel):
    instructor_id: str = Field(..., min_length=1)
    instructor_name: str = "Instructor"
    department: str = Field(..., min_length=1)
    year: str = Field(..., min_length=1)
    section: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    total_students: int = 0

class VerifyQRRequest(BaseModel):
    roll_number: str = Field(..., min_length=1)
    qr_token: str = Field(..., min_length=1)

class VerifyGrantRequest(BaseModel):
    grant_id: str = Field(..., min_length=1)
    roll_number: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)

class ConsumeGrantRequest(BaseModel):
    grant_id: str = Field(..., min_length=1)

class IncrementRetryRequest(BaseModel):
    grant_id: str = Field(..., min_length=1)

@app.post("/session/start")
async def start_session(req: SessionStartRequest):
    session, error = store.start_session(req.instructor_id, req.department, req.year, req.section, req.subject, req.instructor_name, req.total_students)
    if error: return standard_response(False, error, status_code=400)
    return standard_response(True, "Session started", {"session_id": session["id"], "total_students": session.get("total_students", 0)})

@app.get("/session/current-qr")
async def get_current_qr(instructor_id: str = Query(..., min_length=1)):
    session = store.get_active_session(instructor_id)
    if not session: return standard_response(False, "No active session", status_code=404)
    code, expiry = store.generate_fresh_code(instructor_id, QR_EXPIRY_SECONDS)
    return standard_response(True, "Fresh code generated", {"qr_token": code, "expires_at": expiry.isoformat(), "ttl": QR_EXPIRY_SECONDS})

@app.get("/session/status")
async def get_status(instructor_id: str = Query(..., min_length=1)):
    session = store.get_active_session(instructor_id)
    return standard_response(True, "Status fetched", {"active": session is not None, "session_id": session["id"] if session else None, "class_name": session["class_name"] if session else None})

@app.post("/session/stop")
async def stop_session(instructor_id: str = Body(..., embed=True)):
    session, error = store.stop_session(instructor_id)
    if error: return standard_response(False, error, status_code=404)
    try:
        # Trigger report generation in background
        async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
            await client.post(f"https://127.0.0.1:5003/attendance/session/{session['id']}/generate-report")
    except Exception as e: logger.error(f"Excel trigger failed: {e}")
    return standard_response(True, "Session stopped", {"session_id": session["id"]})

@app.post("/session/increment-retry")
async def increment_retry(req: IncrementRetryRequest):
    count = store.increment_grant_retry(req.grant_id)
    return standard_response(True, "Retry incremented", {"retry_count": count})

@app.post("/session/verify-qr")
async def verify_qr(req: VerifyQRRequest):
    session, error = store.verify_code(req.qr_token.strip())
    if error: return standard_response(False, error, error_code=f"QR_{error}", status_code=401)
    grant = store.create_grant(req.roll_number.upper().strip(), session["id"], session["instructor_id"])
    return standard_response(True, "QR validated", {"grant_id": grant["grant_id"], "session_id": grant["session_id"], "instructor_id": grant["instructor_id"], "expires_in": 30})

@app.post("/session/verify-grant")
async def verify_grant(req: VerifyGrantRequest):
    grant, error = store.verify_grant(req.grant_id, req.roll_number, req.session_id)
    if error: return standard_response(False, error, error_code=error, status_code=401)
    return standard_response(True, "Grant valid", {"instructor_id": grant["instructor_id"]})

@app.post("/session/consume-grant")
async def consume_grant(req: ConsumeGrantRequest):
    success = store.consume_grant(req.grant_id)
    if not success: return standard_response(False, "Grant consumption failed", error_code="GRANT_CONSUME_FAILED", status_code=400)
    return standard_response(True, "Grant consumed")

@app.get("/session/{session_id}")
async def get_session(session_id: str):
    session = store.get_session_by_id(session_id)
    if not session: return standard_response(False, "Session not found", status_code=404)
    data = session.copy()
    for k in ["created_at", "start_time", "end_time"]:
        if k in data and data[k]: data[k] = data[k].isoformat()
    return standard_response(True, "Found", data)

@app.get("/health")
async def health(): return {"status": "ok"}
