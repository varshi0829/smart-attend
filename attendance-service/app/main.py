import httpx
import time
import logging
import os
import socket
import sys
import platform
import traceback
import csv
from datetime import datetime, timezone
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from .responses import standard_response
from .integrations import verify_face, verify_qr, verify_grant, consume_grant
from .storage import db
from .config import FACE_SERVICE_URL, QR_SERVICE_URL, BACKEND_URL, ENABLE_DAILY_LIMIT, ATTENDANCE_TIMEZONE, SERVICE_TIMEOUT, LOG_LEVEL, INTERNAL_TLS_VERIFY, REPORTS_DIR

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
    async with httpx.AsyncClient(verify=INTERNAL_TLS_VERIFY) as client:
        try:
            res = await client.get(f"{url}/health", timeout=2.0)
            return {
                "status": "UP" if res.status_code == 200 else "DOWN", 
                "details": res.json() if res.status_code == 200 else None
            }
        except Exception as e:
            return {"status": "DOWN", "error": repr(e)}

def _log_runtime_diagnostics() -> None:
    logger.info(
        "[STARTUP] Runtime: python=%s platform=%s",
        sys.version.split(" ")[0],
        platform.platform(),
    )
    logger.info(
        "[STARTUP] Config: FACE_SERVICE_URL=%s QR_SERVICE_URL=%s INTERNAL_TLS_VERIFY=%s",
        FACE_SERVICE_URL,
        QR_SERVICE_URL,
        INTERNAL_TLS_VERIFY,
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
    logger.info("[STARTUP] Attendance service preflight started.")
    try:
        # Ensure reports directory exists
        os.makedirs(REPORTS_DIR, exist_ok=True)
        _log_runtime_diagnostics()
        _validate_socket_runtime_permissions()
        face_status = await get_service_status(FACE_SERVICE_URL)
        qr_status = await get_service_status(QR_SERVICE_URL)
        logger.info("[STARTUP] Dependency health snapshot: face=%s qr=%s", face_status, qr_status)
    except Exception as exc:
        logger.error(f"[STARTUP] Preflight failed: {exc}\n{traceback.format_exc()}")
        raise
    logger.info("[STARTUP] Attendance service preflight completed successfully.")

def load_student_records():
    """Load all student records from CSV into a searchable format."""
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "backend", "students.csv")
    roll_to_name = {}
    section_to_students = {}
    
    if not os.path.exists(csv_path):
        logger.error(f"Students CSV not found at {csv_path}")
        return roll_to_name, section_to_students

    try:
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                roll = row.get("rollnumber", "").strip().upper()
                name = row.get("name", "").strip()
                sec = row.get("section", "").strip().upper()
                
                if roll:
                    roll_to_name[roll] = name
                    if sec not in section_to_students:
                        section_to_students[sec] = []
                    section_to_students[sec].append({"roll_number": roll, "name": name})
    except Exception as e:
        logger.error(f"Error loading students CSV: {e}")
        
    return roll_to_name, section_to_students

async def generate_excel_task(session_id: str):
    """Background task to generate Excel report with 12-hour IST format and strict header."""
    logger.info(f"[EXCEL] Generating report for session: {session_id}")
    try:
        from zoneinfo import ZoneInfo
        IST = ZoneInfo(ATTENDANCE_TIMEZONE)

        # 1. Fetch Session Details from Backend
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BACKEND_URL}/api/instructor/session/{session_id}")
            if resp.status_code != 200:
                logger.error(f"Failed to fetch session details for {session_id}")
                return None
            session_data = resp.json().get("session", {})

        # 2. Extract Header Info & Section Mapping
        instructor = session_data.get("instructor", {})
        teacher_name = instructor.get("name", "N/A")
        teacher_id = str(instructor.get("_id", "N/A"))
        subject = session_data.get("subject", "N/A")
        class_name = session_data.get("className", "N/A")
        # Fix: Extract correct section from className (e.g., CSE-A)
        section = class_name.strip().upper() 

        start_time_raw = session_data.get("startTime")
        stop_time_raw = session_data.get("stopTime") or datetime.now(timezone.utc).isoformat()

        # Format times to 12-hour IST
        start_dt = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00")).astimezone(IST)
        stop_dt = datetime.fromisoformat(stop_time_raw.replace("Z", "+00:00")).astimezone(IST)
        date_str = start_dt.strftime("%Y-%m-%d")
        start_time_str = start_dt.strftime("%I:%M:%S %p")
        stop_time_str = stop_dt.strftime("%I:%M:%S %p")

        # 3. Load Student Data
        roll_to_name, section_to_students = load_student_records()
        
        # 4. Fetch Present Students
        present_records = {r["roll_number"]: r for r in db.get_by_session(session_id)}
        all_students = section_to_students.get(section, [])
        
        if not all_students:
            logger.warning(f"No students found for section {section}. Using present list fallback.")
            all_students = [{"roll_number": k, "name": roll_to_name.get(k, "Unknown Student")} for k in present_records.keys()]

        # 5. Build Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "Attendance Report"

        # Styles
        header_font = Font(bold=True)
        border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

        # Header Section (Top)
        ws.append(["Teacher Name", teacher_name])
        ws.append(["Teacher ID", teacher_id])
        ws.append(["Subject", subject])
        ws.append(["Class", class_name])
        ws.append(["Section", section])
        ws.append(["Session ID", session_id])
        ws.append(["Date", date_str])
        ws.append(["Start Time", start_time_str])
        ws.append(["End Time", stop_time_str])
        
        for row in ws.iter_rows(min_row=1, max_row=9, max_col=1):
            for cell in row: cell.font = header_font

        # Main Table Header
        ws.append([]) # Spacer
        table_header_row = 11
        cols = ["S.No", "Roll Number", "Student Name", "Status", "Marked Time"]
        ws.append(cols)
        for cell in ws[table_header_row]:
            cell.font = header_font
            cell.border = border

        # Table Data
        all_students.sort(key=lambda x: x["roll_number"])
        present_count = 0
        for i, student in enumerate(all_students, 1):
            roll = student["roll_number"]
            name = student["name"]
            is_present = roll in present_records
            
            marked_time = ""
            if is_present:
                present_count += 1
                ts = present_records[roll]["timestamp"]
                m_dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(IST)
                marked_time = m_dt.strftime("%I:%M:%S %p")

            row_data = [i, roll, name, "Present" if is_present else "Absent", marked_time]
            ws.append(row_data)
            for cell in ws[ws.max_row]: cell.border = border

        # Bottom Summary
        ws.append([]) # Spacer
        ws.append(["Total Students", len(all_students)])
        ws.append(["Total Present", present_count])
        ws.append(["Total Absent", len(all_students) - present_count])
        
        for row in ws.iter_rows(min_row=ws.max_row-2, max_row=ws.max_row, max_col=1):
            for cell in row: cell.font = header_font

        # Save with Required Naming Format
        filename = f"attendance_{section}_{date_str}_session_{session_id}.xlsx"
        filepath = os.path.join(REPORTS_DIR, filename)
        wb.save(filepath)
        logger.info(f"Report generated: {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"Error in generate_excel_task: {e}\n{traceback.format_exc()}")
        return None

@app.post("/attendance/session/{session_id}/generate-report")
async def trigger_report_generation(session_id: str, background_tasks: BackgroundTasks):
    """Endpoint to trigger Excel generation."""
    background_tasks.add_task(generate_excel_task, session_id)
    return standard_response(True, "Report generation started in background.")

@app.get("/attendance/session/{session_id}/download-report")
async def download_report(session_id: str):
    """Find and download the latest report for this session."""
    try:
        # Search for files containing the session ID
        files = [f for f in os.listdir(REPORTS_DIR) if session_id in f and f.endswith(".xlsx")]
        if not files:
            # Try generating it synchronously if not found
            path = await generate_excel_task(session_id)
            if not path:
                return standard_response(False, "Report not found and could not be generated.", status_code=404)
            return FileResponse(path, filename=os.path.basename(path))

        # Return the most recent file matching the session ID
        files.sort(key=lambda x: os.path.getmtime(os.path.join(REPORTS_DIR, x)), reverse=True)
        path = os.path.join(REPORTS_DIR, files[0])
        return FileResponse(path, filename=os.path.basename(path))
    except Exception as e:
        return standard_response(False, f"Download failed: {str(e)}", status_code=500)

@app.get("/debug/pipeline")
async def debug_pipeline():
    qr_status = await get_service_status(QR_SERVICE_URL)
    face_status = await get_service_status(FACE_SERVICE_URL)
    
    last = db.get_last_attempt()
    student_debug = None
    
    if last and last.get("roll_number"):
        try:
            async with httpx.AsyncClient(verify=INTERNAL_TLS_VERIFY) as client:
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
    grant_id: str = Form(...),
    session_id: str = Form(...),
    image: UploadFile = File(...)
):
    start_time = time.time()
    roll_no = roll_number.strip().upper()
    grant_id = grant_id.strip()
    session_id = session_id.strip()
    
    if not roll_no or not grant_id or not session_id:
        return standard_response(False, "Roll number, Grant ID, and Session ID are required.", error_code="INVALID_INPUT", status_code=400)
    
    image_bytes = await image.read()
    if not image_bytes:
        return standard_response(False, "Image file is empty.", error_code="INVALID_INPUT", status_code=400)

    # Grant Verification (replaces QR verification for this final step)
    logger.info(f"[PIPELINE] Starting Grant verification for roll={roll_no}, grant_id={grant_id}")
    g_res, g_status = await verify_grant(grant_id, roll_no, session_id)
    if g_status != 200 or not g_res.get("success"):
        error_code = g_res.get("error_code", "GRANT_VALIDATION_FAILED")
        msg = g_res.get("message", "Scan grant validation failed")
        logger.warning(f"[PIPELINE] Grant verification FAILED: error_code={error_code}, msg={msg}")
        db.set_last_attempt(roll_no, "FAILED_GRANT", {"error_code": error_code, "msg": msg})
        return standard_response(False, msg, error_code=error_code, status_code=g_status if g_status < 500 else 503)

    # Face Verification
    logger.info(f"[PIPELINE] Starting Face verification for roll={roll_no}")
    face_res, face_status = await verify_face(roll_no, image_bytes, image.filename)
    if face_status != 200 or not face_res.get("success"):
        error_code = face_res.get("error_code", "FACE_VERIFICATION_FAILED")
        msg = face_res.get("message", "Face verification failed")
        # NOTE: We do NOT consume the grant on face failure so student can retry
        db.set_last_attempt(roll_no, "FAILED_FACE", {"error_code": error_code, "msg": msg})
        return standard_response(False, msg, error_code=error_code, status_code=face_status if face_status < 500 else 503)

    grant_data = g_res.get("data", {})
    instructor_id = grant_data.get("instructor_id", "UNKNOWN")

    # Atomic Save Attendance
    record, error = db.mark_attendance_atomic(
        roll_no, 
        session_id, 
        instructor_id, 
        face_res.get("confidence", 0.0),
        enable_daily_limit=ENABLE_DAILY_LIMIT
    )

    if error:
        # If it's a known conflict, consume the grant to mark this attempt as 'done' 
        # and prevent replay, then return the conflict error.
        if error in ["DUPLICATE_ATTENDANCE", "DAILY_LIMIT_REACHED"]:
            await consume_grant(grant_id)
            
        db.set_last_attempt(roll_no, "DENIED", {"error_code": error})
        msg = "Attendance already marked for this session." if error == "DUPLICATE_ATTENDANCE" else "Attendance already marked for today."
        return standard_response(False, msg, error_code=error, status_code=400)

    # Success! Now consume the grant to finalize.
    c_res, c_status = await consume_grant(grant_id)
    if c_status != 200 or not c_res.get("success"):
        # This is a rare edge case where attendance saved but grant consumption failed.
        # Since attendance IS saved, we still return success to the student.
        logger.error(f"[PIPELINE] Attendance saved but grant consumption failed: {grant_id}")

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
                # Robust parsing for ISO format with Z or numerical offset
                parsed_ts = ts.replace("Z", "+00:00")
                dt = datetime.fromisoformat(parsed_ts)
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
    """Look up student name from CSV mapping."""
    roll_to_name, _ = load_student_records()
    return roll_to_name.get(roll_number.strip().upper(), "Unknown Student")

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "face_service_url": FACE_SERVICE_URL,
        "qr_service_url": QR_SERVICE_URL,
        "internal_tls_verify": INTERNAL_TLS_VERIFY,
    }
