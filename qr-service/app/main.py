import time
from fastapi import FastAPI, Query, Body, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import logging
import platform
import socket
import sys
import traceback
from .session_store import store
from .responses import standard_response
from .config import QR_EXPIRY_SECONDS

app = FastAPI(title="SmartAttend QR Session Service")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QRService")

# Allow any origin for local network access (development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _log_runtime_diagnostics() -> None:
    logger.info(
        "[STARTUP] Runtime: python=%s platform=%s qr_expiry=%s",
        sys.version.split(" ")[0],
        platform.platform(),
        QR_EXPIRY_SECONDS,
    )

def _validate_socket_runtime_permissions() -> None:
    probe = None
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except PermissionError as exc:
        logger.warning(
            "[STARTUP] Socket runtime check warning: %s. "
            "Continuing startup; uvicorn bind step will report concrete bind errors if restricted.",
            exc,
        )
        return
    except OSError as exc:
        logger.warning(
            "[STARTUP] Socket runtime check warning (OS error): %s. "
            "Continuing startup; uvicorn bind step will report concrete bind errors if restricted.",
            exc,
        )
        return
    finally:
        if probe is not None:
            probe.close()

@app.on_event("startup")
async def startup_preflight():
    logger.info("[STARTUP] QR service preflight started.")
    try:
        _log_runtime_diagnostics()
        _validate_socket_runtime_permissions()
    except Exception as exc:
        logger.error(f"[STARTUP] Preflight failed: {exc}\n{traceback.format_exc()}")
        raise
    logger.info("[STARTUP] QR service preflight completed successfully.")

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    started = time.time()
    try:
        response = await call_next(request)
        elapsed_ms = int((time.time() - started) * 1000)
        logger.info(
            "[REQUEST] %s %s -> %s (%sms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
    except Exception:
        elapsed_ms = int((time.time() - started) * 1000)
        logger.error(
            "[REQUEST] %s %s -> EXCEPTION (%sms)\n%s",
            request.method,
            request.url.path,
            elapsed_ms,
            traceback.format_exc(),
        )
        raise

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "[UNHANDLED] %s %s failed: %r\n%s",
        request.method,
        request.url.path,
        exc,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error", "error_code": "SERVER_ERROR"},
    )

class SessionStartRequest(BaseModel):
    instructor_id: str = Field(..., min_length=1)
    class_name: str = Field(..., min_length=1)

class VerifyQRRequest(BaseModel):
    roll_number: str = Field(..., min_length=1)
    qr_token: str = Field(..., min_length=1)

class VerifyGrantRequest(BaseModel):
    grant_id: str = Field(..., min_length=1)
    roll_number: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)

class ConsumeGrantRequest(BaseModel):
    grant_id: str = Field(..., min_length=1)

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
    roll_no = req.roll_number.upper().strip()
    
    # Verify the code against the backend store
    session, error = store.verify_code(token)
    
    # Map error codes precisely
    if error == "INVALID_CODE":
        return standard_response(False, "The QR code is invalid or unrecognized.", error_code="QR_INVALID", status_code=401)
    if error == "CODE_EXPIRED":
        return standard_response(False, "This QR code has expired. Please scan the latest one.", error_code="QR_EXPIRED", status_code=401)
    if error == "SESSION_CLOSED":
        return standard_response(False, "The instructor has ended this session.", error_code="SESSION_CLOSED", status_code=400)

    # Create a scan grant for this student
    grant = store.create_grant(roll_no, session["id"], session["instructor_id"])

    # Return required payload including the new grant_id
    return standard_response(True, "QR validated successfully", {
        "grant_id": grant["grant_id"],
        "session_id": grant["session_id"],
        "instructor_id": grant["instructor_id"],
        "roll_number": grant["roll_number"],
        "expires_at": grant["expires_at"].isoformat(),
        "expires_in": 30
    })

@app.post("/session/verify-grant")
async def verify_grant(req: VerifyGrantRequest):
    grant, error = store.verify_grant(req.grant_id, req.roll_number, req.session_id)
    if error:
        return standard_response(False, f"Grant verification failed: {error}", error_code=error, status_code=401)
    
    return standard_response(True, "Grant is valid", {
        "grant_id": grant["grant_id"],
        "session_id": grant["session_id"],
        "instructor_id": grant["instructor_id"],
        "roll_number": grant["roll_number"]
    })

@app.post("/session/consume-grant")
async def consume_grant(req: ConsumeGrantRequest):
    success = store.consume_grant(req.grant_id)
    if not success:
        return standard_response(False, "Failed to consume grant", error_code="GRANT_CONSUMPTION_FAILED", status_code=400)
    return standard_response(True, "Grant consumed successfully")

@app.get("/health")
async def health():
    return {"status": "ok", "qr_expiry_seconds": QR_EXPIRY_SECONDS}
