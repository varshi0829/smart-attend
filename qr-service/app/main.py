from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .session_store import store
from .responses import standard_response
from .config import QR_EXPIRY_SECONDS

app = FastAPI(title="SmartAttend QR Session Service")

# CRITICAL: Do NOT use allow_origins=["*"] with allow_credentials=True
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
        "http://localhost:8002",
        "http://127.0.0.1:8002",
        "http://localhost:5500",
        "http://127.0.0.1:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SessionStartRequest(BaseModel):
    instructor_id: str = Field(..., min_length=1)
    class_name: str = Field(..., min_length=1)

class VerifyQRRequest(BaseModel):
    roll_number: str = Field(..., min_length=1)
    qr_token: str = Field(..., min_length=1)

@app.post("/session/start")
async def start_session(req: SessionStartRequest):
    session, error = store.start_session(req.instructor_id, req.class_name)
    if error:
        return standard_response(False, error, status_code=400)
    return standard_response(True, "Session started", {"session_id": session["id"]})

@app.get("/session/current-qr")
async def get_current_qr(instructor_id: str = Query(..., min_length=1)):
    session = store.get_active_session(instructor_id)
    if not session:
        return standard_response(False, "No active session", status_code=404)
    
    code, expiry = store.generate_fresh_code(instructor_id, QR_EXPIRY_SECONDS)
    return standard_response(True, "Fresh code generated", {
        "qr_token": code,
        "expires_at": expiry.isoformat(),
        "ttl": QR_EXPIRY_SECONDS
    })

@app.get("/session/status")
async def get_status(instructor_id: str = Query(..., min_length=1)):
    session = store.get_active_session(instructor_id)
    return standard_response(True, "Status fetched", {
        "active": session is not None,
        "session_id": session["id"] if session else None,
        "class_name": session["class_name"] if session else None
    })

@app.post("/session/stop")
async def stop_session(instructor_id: str = Body(..., embed=True)):
    session, error = store.stop_session(instructor_id)
    if error:
        return standard_response(False, error, status_code=404)
    return standard_response(True, "Session stopped", {"session_id": session["id"]})

@app.post("/session/verify-qr")
async def verify_qr(req: VerifyQRRequest):
    # Strip whitespace from token
    token = req.qr_token.strip()
    
    # Verify the code against the backend store
    session, error = store.verify_code(token)
    
    # Map error codes precisely
    if error == "INVALID_CODE":
        return standard_response(False, "The QR code is invalid or unrecognized.", error_code="QR_INVALID", status_code=401)
    if error == "CODE_EXPIRED":
        return standard_response(False, "This QR code has expired. Please scan the latest one.", error_code="QR_EXPIRED", status_code=401)
    if error == "SESSION_CLOSED":
        return standard_response(False, "The instructor has ended this session.", error_code="SESSION_CLOSED", status_code=400)

    # Return required payload for attendance-service
    return standard_response(True, "QR validated successfully", {
        "session_id": session["id"],
        "instructor_id": session["instructor_id"],
        "roll_number": req.roll_number.upper()
    })

@app.get("/health")
async def health():
    return {"status": "ok"}
