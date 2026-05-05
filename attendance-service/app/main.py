import asyncio
import httpx
import time
import logging
import os
import csv
import json
import traceback
import threading
from datetime import datetime, timezone
from typing import List, Dict, Optional
from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    BackgroundTasks,
    HTTPException,
    Query,
)
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from .responses import standard_response
from .integrations import verify_face, verify_qr, verify_grant, consume_grant
from .storage import db
from .config import (
    FACE_SERVICE_URL,
    QR_SERVICE_URL,
    ATTENDANCE_TIMEZONE,
    INTERNAL_TLS_VERIFY,
    REPORTS_DIR,
    logger,
)
from zoneinfo import ZoneInfo
from .mailer import (
    lookup_faculty_details,
    resolve_recipient_email,
    generate_excel_bytes,
    send_attendance_email,
)

app = FastAPI(title="SmartAttend Attendance Orchestrator")
STUDENT_CACHE = None
LOCAL_TZ = ZoneInfo(ATTENDANCE_TIMEZONE)

# ── Report readiness state ────────────────────────────────────────────────────
# Tracks per-session report generation state: "generating" | "ready" | "failed"
# In-memory only; cleared on restart (DB/file fallback used for persistence).
_report_states: Dict[str, str] = {}
_report_states_lock = threading.Lock()


def _set_report_state(session_id: str, status: str):
    with _report_states_lock:
        _report_states[session_id] = status


def _get_report_state(session_id: str) -> str:
    """
    Returns current report generation state for session_id.
    Priority: in-memory dict → DB status → JSON file on disk → "unknown"
    """
    with _report_states_lock:
        if session_id in _report_states:
            return _report_states[session_id]

    # DB fallback: if session is finalized in DB, it's ready
    if pg_db.is_db_available():
        sess = pg_db.get_session_by_id_from_db(session_id)
        if sess and sess.get("status") == "ended":
            return "ready"

    # File fallback: look for any .json report file for this session
    try:
        for root, dirs, files in os.walk(REPORTS_DIR):
            for f in files:
                if f.endswith(".json") and session_id[:8] in f:
                    return "ready"
    except Exception:
        pass

    return "unknown"


# ── Finalized session cache ───────────────────────────────────────────────────
# Stores finalized session data IMMEDIATELY after session stops
# Used by send-mail as fallback when DB is not yet updated
_finalized_sessions: Dict[str, dict] = {}
_finalized_sessions_lock = threading.Lock()


def cache_finalized_session(session_id: str, session_data: dict):
    """Cache finalized session data for immediate mail flow"""
    with _finalized_sessions_lock:
        _finalized_sessions[session_id] = session_data
    logger.info(
        f"[CACHE] Finalized session {session_id[:8]} cached for immediate mail flow"
    )


def get_finalized_session(session_id: str) -> Optional[dict]:
    """Get cached finalized session data"""
    with _finalized_sessions_lock:
        return _finalized_sessions.get(session_id)


# ── Attendance records cache ─────────────────────────────────────────────────
# Stores attendance records immediately as they're marked
_attendance_cache: Dict[str, list] = {}
_attendance_cache_lock = threading.Lock()


def cache_attendance_records(session_id: str, records: list):
    """Cache attendance records for the session"""
    with _attendance_cache_lock:
        _attendance_cache[session_id] = records


def get_cached_attendance(session_id: str) -> list:
    """Get cached attendance records"""
    with _attendance_cache_lock:
        return _attendance_cache.get(session_id, [])


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Orchestrator")

from . import db as pg_db


def load_student_records():
    global STUDENT_CACHE
    if STUDENT_CACHE is not None:
        return STUDENT_CACHE["names"], STUDENT_CACHE["sections"]

    # 1. Try DB
    if pg_db.is_db_available():
        names, sections = pg_db.get_students()
        if names:
            STUDENT_CACHE = {"names": names, "sections": sections}
            logger.info(f"SUCCESS: Loaded {len(names)} students from DB.")
            return names, sections

    # 2. Fallback to CSV
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "..", "backend", "students.csv"
    )
    roll_to_name, roll_to_sec = {}, {}
    if not os.path.exists(csv_path):
        logger.error(f"CRITICAL: students.csv not found at {csv_path}")
        return {}, {}
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                r = row.get("rollnumber", "").strip().upper()
                if not r:
                    continue
                roll_to_name[r] = row.get("name", "").strip()
                roll_to_sec[r] = row.get("section", "").strip().upper()
        STUDENT_CACHE = {"names": roll_to_name, "sections": roll_to_sec}
        logger.info(f"SUCCESS: Loaded {len(roll_to_name)} students from CSV.")
    except Exception as e:
        logger.error(f"CSV load failed: {e}")
    return roll_to_name, roll_to_sec


@app.get("/faculty/assignments")
async def get_assignments(teacher_name: str):
    """Role-based assignment fetch"""
    # 1. Try DB
    if pg_db.is_db_available():
        teacher = pg_db.get_teacher_by_name(teacher_name)
        if teacher:
            role = teacher["role"]
            if role == "principal":
                return standard_response(
                    True, "All assignments (Principal)", pg_db.get_all_assignments()
                )
            elif role == "hod":
                all_as = pg_db.get_all_assignments()
                dept_as = [
                    a for a in all_as if a.get("teacher_dept") == teacher["department"]
                ]
                return standard_response(
                    True, f"Department assignments ({teacher['department']})", dept_as
                )
            else:
                return standard_response(
                    True,
                    "Your assignments",
                    pg_db.get_teacher_assignments(teacher["id"]),
                )

    # 2. Fallback to JSON
    json_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "..",
        "frontend-instructor",
        "faculty_assignments.json",
    )
    if os.path.exists(json_path):
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
                faculty_data = data.get("faculty", {}).get(teacher_name.lower())
                if faculty_data:
                    return standard_response(
                        True, "Found (JSON)", faculty_data.get("assignments", [])
                    )
        except Exception as e:
            logger.error(f"JSON load failed: {e}")

    return standard_response(False, "Assignments not found", status_code=404)


async def get_session_meta(sid: str):
    async with httpx.AsyncClient(verify=INTERNAL_TLS_VERIFY) as client:
        try:
            res = await client.get(f"{QR_SERVICE_URL}/session/{sid}", timeout=5.0)
            return res.json().get("data") if res.status_code == 200 else None
        except Exception as e:
            logger.error(f"Failed to fetch session meta for {sid}: {e}")
            return None


@app.get("/attendance/student-count")
async def get_student_count(
    dept: str = Query(...), year: int = Query(...), section: str = Query(...)
):
    """Get student count for a specific department/year/section"""
    # 1. Try DB first
    count = pg_db.get_student_count(dept, year, section)
    if count > 0:
        return standard_response(True, "Count retrieved", {"count": count})

    # 2. Fallback to CSV - load and count
    names, sections = load_student_records()
    section_code = f"{dept.upper()}-{section.upper()}"
    count = sum(1 for s in sections.values() if s.upper() == section_code)
    return standard_response(True, "Count retrieved", {"count": count})


@app.post("/attendance/mark")
async def mark_attendance(
    roll_number: str = Form(...),
    grant_id: str = Form(...),
    session_id: str = Form(...),
    image: UploadFile = File(...),
):
    roll_no = roll_number.strip().upper()

    # 1. Eligibility Check
    meta = await get_session_meta(session_id)
    if not meta:
        return standard_response(False, "Session not found", status_code=404)

    names, sections = load_student_records()
    if roll_no not in sections:
        return standard_response(False, "Student record not found", status_code=404)

    if sections[roll_no] != meta.get("class_name"):
        return standard_response(
            False,
            f"You belong to {sections[roll_no]}, but this session is for {meta['class_name']}",
            error_code="STUDENT_NOT_IN_SESSION_CLASS",
            status_code=403,
        )

    # Phase C: Upsert session row into DB before any attendance insert.
    # The attendance table has a FK on session_id → sessions.session_id.
    # Sessions are created in QR service memory and only written to the sessions
    # table at session END (in generate_excel_task). Without this upsert the first
    # attendance INSERT violates the FK constraint.
    if pg_db.is_db_available():
        pg_db.save_session_full(
            session_id=session_id,
            teacher_id=meta.get("instructor_id", ""),
            teacher_name=meta.get("instructor_name", ""),
            department=meta.get("department", ""),
            year=str(meta.get("year", "")),
            section=meta.get("section", ""),
            subject=meta.get("subject", ""),
            start_time=meta.get("start_time"),
        )

    # 2. Grant Verify
    g_res, g_status = await verify_grant(grant_id, roll_no, session_id)
    if g_status != 200:
        return standard_response(
            False,
            g_res.get("message"),
            error_code=g_res.get("error_code"),
            status_code=g_status,
        )

    # 3. Face Verify
    img_bytes = await image.read()
    f_res, f_status = await verify_face(roll_no, img_bytes, image.filename)
    if f_status != 200 or not f_res.get("success"):
        error_code = f_res.get("error_code", "FACE_FAILED")
        msg = f_res.get("message", "Face verification failed")

        # Increment retry count in QR service
        retry_count = 0
        try:
            async with httpx.AsyncClient(verify=INTERNAL_TLS_VERIFY) as client:
                r_resp = await client.post(
                    f"{QR_SERVICE_URL}/session/increment-retry",
                    json={"grant_id": grant_id},
                    timeout=5.0,
                )
                retry_count = r_resp.json().get("data", {}).get("retry_count", 0)
                if retry_count >= 3:
                    msg = "Face verification failed 3 times. This QR grant is now invalid. Please re-scan."
                    error_code = "GRANT_RETRY_LIMIT_REACHED"
        except Exception as e:
            logger.error(f"[PIPELINE] Failed to increment retry count: {e}")

        db.set_last_attempt(
            roll_no, "FAILED_FACE", {"error_code": error_code, "msg": msg}
        )
        return standard_response(
            False,
            msg,
            error_code=error_code,
            status_code=f_status if f_status < 500 else 503,
        )

    # 4. Atomic Save
    record, err = db.mark_attendance_atomic(
        roll_no, session_id, meta["instructor_id"], f_res.get("confidence", 0.0)
    )
    if err:
        return standard_response(
            False, "Attendance already marked", error_code=err, status_code=400
        )

    await consume_grant(grant_id)
    return standard_response(True, "Success", data=record)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1: Session finalization helper
# Called from generate_excel_task after session ends.
# ─────────────────────────────────────────────────────────────────────────────


def finalize_session_in_db(session_id: str, meta: dict, records: dict, names: dict):
    """
    Persist the finalized session summary and enrich attendance rows with names.

    meta:    session dict from QR service (has instructor_id, instructor_name,
             department, year, section, subject, start_time, end_time, total_students)
    records: {roll_number: attendance_record} from in-memory store
    names:   {roll_number: student_name} from load_student_records()

    """
    if not pg_db.is_db_available():
        logger.info(
            f"[DB] DB not available — skipping DB finalization for {session_id}"
        )
        return

    try:
        # 1. Upsert the session row (handles case where session was never saved to DB at start)
        pg_db.save_session_full(
            session_id=session_id,
            teacher_id=meta.get("instructor_id", ""),
            teacher_name=meta.get("instructor_name", ""),
            department=meta.get("department", ""),
            year=str(meta.get("year", "")),
            section=meta.get("section", ""),
            subject=meta.get("subject", ""),
            start_time=meta.get("start_time"),
        )

        # 2. Compute summary counts
        present_count = len(records)
        total_count = meta.get("total_students", 0)
        absent_count = max(0, total_count - present_count)

        faculty = lookup_faculty_details(
            teacher_name=meta.get("instructor_name", ""),
            teacher_id=meta.get("instructor_id", ""),
            department=meta.get("department", ""),
            year=str(meta.get("year", "")),
            section=meta.get("section", ""),
            subject=meta.get("subject", ""),
        )

        pg_db.finalize_session(
            session_id=session_id,
            teacher_name=meta.get("instructor_name", ""),
            ended_at=meta.get("end_time"),
            present_count=present_count,
            total_count=total_count,
            absent_count=absent_count,
            teacher_email=faculty.get("email"),
            semester=(faculty.get("assignment") or {}).get("semester"),
        )

        # 3. Enrich attendance rows in DB with student names
        roll_name_map = {
            roll: names.get(roll.strip().upper(), "Unknown") for roll in records
        }
        pg_db.update_attendance_student_names(session_id, roll_name_map)

        logger.info(
            f"[DB] Session {session_id} finalized — "
            f"present: {present_count}, total: {total_count}, absent: {absent_count}"
        )

    except Exception as e:
        logger.error(
            f"[DB] Finalization failed for {session_id}: {e}\n{traceback.format_exc()}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Report generation (Excel + JSON mirror + DB finalization)
# ─────────────────────────────────────────────────────────────────────────────


async def generate_excel_task(session_id: str):
    logger.info(
        f"[REPORT] ========== REPORT GENERATION STARTED for session: {session_id} =========="
    )
    _set_report_state(session_id, "generating")
    try:
        meta = await get_session_meta(session_id)
        if not meta:
            logger.error(f"[REPORT] Meta not found for {session_id}")
            _set_report_state(session_id, "failed")
            return

        from zoneinfo import ZoneInfo

        IST = ZoneInfo(ATTENDANCE_TIMEZONE)
        start_dt = datetime.fromisoformat(meta["start_time"]).astimezone(IST)

        # Path: reports/inst_id/dept/year/section/
        class_dir = os.path.join(
            REPORTS_DIR,
            meta["instructor_id"],
            meta["department"],
            meta["year"],
            meta["section"],
        )
        os.makedirs(class_dir, exist_ok=True)

        records = {r["roll_number"]: r for r in db.get_by_session(session_id)}
        names, sections = load_student_records()
        target_students = [r for r in sections if sections[r] == meta["class_name"]]

        wb = Workbook()
        ws = wb.active
        ws.append(
            [
                "Subject",
                meta["subject"],
                "Class",
                meta["class_name"],
                "Date",
                start_dt.strftime("%Y-%m-%d"),
            ]
        )
        ws.append(["S.No", "Roll Number", "Name", "Status", "Time"])

        for i, roll in enumerate(sorted(target_students), 1):
            is_p = roll in records
            ws.append(
                [
                    i,
                    roll,
                    names.get(roll, "Unknown"),
                    "Present" if is_p else "Absent",
                    records[roll]["timestamp"] if is_p else "",
                ]
            )

        filename = f"{start_dt.strftime('%H%M')}_{session_id[:8]}.xlsx"
        fpath = os.path.join(class_dir, filename)
        wb.save(fpath)
        logger.info(f"[REPORT] Excel saved: {fpath}")

        # Enrich records with names for the JSON viewer mirror
        enriched_attendance = []
        for roll, rec in records.items():
            normalized_roll = roll.strip().upper()
            rec_copy = rec.copy()
            rec_copy["name"] = names.get(normalized_roll, "Unknown Student")
            enriched_attendance.append(rec_copy)

        # Save JSON mirror for high-speed in-app viewing
        # Include mail_sent fields so file-backed history also has them
        meta_with_mail = dict(meta)
        meta_with_mail.setdefault("mail_sent", False)
        meta_with_mail.setdefault("mail_sent_at", None)
        # Ensure total_students is included for mail/Excel flow
        if "total_students" not in meta_with_mail and "total_students" in meta:
            meta_with_mail["total_students"] = meta["total_students"]
        with open(fpath.replace(".xlsx", ".json"), "w") as jf:
            json.dump({"meta": meta_with_mail, "attendance": enriched_attendance}, jf)
        logger.info(
            f"[REPORT] JSON mirror saved with {len(enriched_attendance)} enriched records."
        )

        # ── Phase 1: Persist finalized session to DB ──────────────────────────
        finalize_session_in_db(session_id, meta, records, names)

        # ── Cache finalized session + attendance for immediate mail flow ──────
        cache_finalized_session(session_id, meta_with_mail)
        cache_attendance_records(session_id, enriched_attendance)
        logger.info(
            f"[CACHE] Cached session data for mail flow - session: {session_id[:8]}, total_students: {meta_with_mail.get('total_students', 'N/A')}"
        )

        _set_report_state(session_id, "ready")
        logger.info(
            f"[REPORT] ========== REPORT GENERATION COMPLETED for session: {session_id} =========="
        )

    except Exception as e:
        logger.error(
            f"[REPORT] ========== REPORT GENERATION FAILED for session: {session_id} =========="
        )
        logger.error(f"[REPORT] Generation failed: {e}\n{traceback.format_exc()}")
        _set_report_state(session_id, "failed")


@app.post("/attendance/session/{session_id}/generate-report")
async def trigger_report(session_id: str, background_tasks: BackgroundTasks):
    logger.info(
        f"[REPORT] Received trigger for session {session_id} — queued in background"
    )
    background_tasks.add_task(generate_excel_task, session_id)
    return standard_response(True, "Started")


@app.get("/attendance/sessions/{session_id}/report-status")
async def get_report_status(session_id: str):
    """
    Lightweight poll endpoint — returns report generation state for a session.
    States: "generating" | "ready" | "failed" | "unknown"
    Frontend polls this every 1-2 s after stopping a session.
    """
    status = _get_report_state(session_id)
    return standard_response(True, status, {"status": status})


# ─────────────────────────────────────────────────────────────────────────────
# Reports — list, download, viewer
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/reports/list")
async def list_reports(instructor_id: str, dept: str, year: str, sec: str):
    """
    Return session history for a specific instructor+class.

    Priority:
      1. PostgreSQL (get_ended_sessions) — newest first, includes mail_sent state
      2. JSON files on disk — fallback when DB not available
    """
    names, _ = load_student_records()

    # ── 1. Try DB ──────────────────────────────────────────────────────────
    if pg_db.is_db_available():
        sessions = pg_db.get_ended_sessions(instructor_id, dept, year, sec)
        if sessions:
            results = []
            for s in sessions:
                att = pg_db.get_attendance_by_session_from_db(s["session_id"])
                # Resolve any missing names using the names lookup
                for rec in att:
                    if not rec.get("name") or rec["name"] in (
                        "Unknown",
                        "Unknown Student",
                    ):
                        rec["name"] = names.get(
                            rec["roll_number"].strip().upper(), "Unknown Student"
                        )

                results.append(
                    {
                        "meta": {
                            "id": s["session_id"],
                            "instructor_id": s["teacher_id"],
                            "instructor_name": s["teacher_name"],
                            "department": s["department"],
                            "year": s["year"],
                            "section": s["section"],
                            "subject": s["subject"],
                            "class_name": f"{s['department']}-{s['section']}",
                            "start_time": s["start_time"],
                            "end_time": s["ended_at"],
                            "total_students": s["total_count"],
                            "mail_sent": s["mail_sent"],
                            "mail_sent_at": s["mail_sent_at"],
                            "semester": s["semester"],
                            "status": "ended",
                        },
                        "attendance": att,
                    }
                )
            return standard_response(True, "Found", results)

    # ── 2. Fallback to file system ─────────────────────────────────────────
    path = os.path.join(REPORTS_DIR, instructor_id, dept, year, sec)
    if not os.path.exists(path):
        return standard_response(True, "No reports", [])

    json_files = [f for f in os.listdir(path) if f.endswith(".json")]
    results = []

    for f in json_files:
        try:
            with open(os.path.join(path, f), "r") as jf:
                data = json.load(jf)
                # Resolve missing names
                for record in data.get("attendance", []):
                    roll = record.get("roll_number", "").strip().upper()
                    if roll and (
                        not record.get("name")
                        or record.get("name") in ("N/A", "Unknown Student")
                    ):
                        record["name"] = names.get(roll, "Unknown Student")
                # Ensure mail_sent fields present for backward compat
                if "meta" in data:
                    data["meta"].setdefault("mail_sent", False)
                    data["meta"].setdefault("mail_sent_at", None)
                results.append(data)
        except Exception as e:
            logger.error(f"Error reading report {f}: {e}")

    # Sort newest first by start_time inside the JSON meta
    results.sort(key=lambda x: x.get("meta", {}).get("start_time", ""), reverse=True)

    return standard_response(True, "Found", results)


@app.get("/reports/download")
async def download_report(
    instructor_id: str, dept: str, year: str, sec: str, filename: str
):
    fpath = os.path.join(REPORTS_DIR, instructor_id, dept, year, sec, filename)
    if os.path.exists(fpath):
        return FileResponse(fpath)
    raise HTTPException(status_code=404)


# ─────────────────────────────────────────────────────────────────────────────
# Attendance queries
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/attendance/session/{session_id}")
async def get_session_history(session_id: str):
    records = db.get_by_session(session_id)
    names, _ = load_student_records()
    return standard_response(
        True,
        "History",
        [
            {
                "roll_number": r["roll_number"],
                "name": names.get(r["roll_number"].strip().upper(), "Unknown"),
                "timestamp": r["timestamp"],
            }
            for r in records
        ],
    )


@app.get("/attendance/class-list/{class_name}")
async def get_class_list(class_name: str):
    names, sections = load_student_records()
    target = class_name.upper().strip()
    students = [
        {"roll_number": r, "name": names[r]} for r in sections if sections[r] == target
    ]
    return standard_response(True, f"Found {len(students)} students", students)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2: Send attendance email for a completed session
# ─────────────────────────────────────────────────────────────────────────────


@app.post("/attendance/sessions/{session_id}/send-mail")
async def send_session_mail(session_id: str):
    """
    Send the attendance email for a completed session.

    Flow:
      1. Check report readiness state
      2. Try DB first for session data (primary)
      3. Fallback to cache (immediate post-stop) or JSON file (generated)
      4. Load attendance records (DB or cache)
      5. Duplicate send guard
      6. Resolve recipient email (temporary mapping)
      7. Generate Excel attachment in memory
      8. Send via SMTP
      9. Mark mail_sent in DB + cache

    Returns 422 if faculty email not configured.
    Returns 400 if mail already sent.
    Returns 503 if report not ready.
    """
    logger.info(f"[MAIL] Send mail requested for session: {session_id[:8]}")

    # 1. Check report readiness state (set by generate_excel_task)
    report_state = _get_report_state(session_id)
    logger.info(f"[MAIL] Report state for {session_id[:8]}: {report_state}")
    if report_state == "generating":
        return standard_response(
            False,
            "Session report is still being prepared. Please wait and try again.",
            error_code="REPORT_NOT_READY",
            status_code=503,
        )
    if report_state == "failed":
        return standard_response(
            False,
            "Report generation failed for this session. Check server logs.",
            error_code="REPORT_FAILED",
            status_code=500,
        )

    # 2. Try DB first for session data
    session = None
    mail_sent_flag = False
    if pg_db.is_db_available():
        session = pg_db.get_session_by_id_from_db(session_id)
        if session:
            mail_sent_flag = session.get("mail_sent", False)
            logger.info(
                f"[MAIL] Found session in DB: {session_id[:8]}, mail_sent: {mail_sent_flag}"
            )

    # 2b. Fallback to cache if DB not found
    if not session:
        session = get_finalized_session(session_id)
        if session:
            logger.info(f"[MAIL] Using cached finalized session: {session_id[:8]}")
        else:
            # 2c. Fallback to JSON file if cache not available
            # Try to load from the generated JSON report file
            logger.info(f"[MAIL] Checking JSON file fallback for: {session_id[:8]}")
            # The JSON is stored at: reports/{instructor_id}/{dept}/{year}/{section}/{HHMM}_{session_id[:8]}.json
            # We need to find it - let's check if we can load it from common paths
            for root, dirs, files in os.walk(REPORTS_DIR):
                for f in files:
                    if f.endswith(".json") and session_id[:8] in f:
                        try:
                            with open(os.path.join(root, f), "r") as jf:
                                data = json.load(jf)
                                session = data.get("meta", {})
                                logger.info(f"[MAIL] Found session in JSON file: {f}")
                                break
                        except Exception as e:
                            logger.error(f"[MAIL] Failed to read JSON fallback: {e}")
                if session:
                    break

    # If still no session data, fail
    if not session:
        logger.error(f"[MAIL] No session data found anywhere for: {session_id[:8]}")
        return standard_response(
            False,
            "Session data not found. Please try again in a moment.",
            error_code="SESSION_NOT_FOUND",
            status_code=404,
        )

    # 3. Duplicate send guard - check in both DB and cache
    if mail_sent_flag:
        return standard_response(
            False,
            "Email was already sent for this session.",
            error_code="ALREADY_SENT",
            status_code=400,
        )
    # Also check cache for mail_sent
    cached_session = get_finalized_session(session_id)
    if cached_session and cached_session.get("mail_sent"):
        return standard_response(
            False,
            "Email was already sent for this session.",
            error_code="ALREADY_SENT",
            status_code=400,
        )

    # 4. Resolve recipient email (temporary fallback: Murali Nath → adapasreevarshitha)
    # Session dict may have teacher_name OR instructor_name - check both
    instructor_name = session.get("teacher_name") or session.get("instructor_name", "")
    instructor_id = session.get("teacher_id") or session.get("instructor_id", "")
    logger.info(
        f"[MAIL] Resolving email - instructor_name='{instructor_name}', instructor_id='{instructor_id}'"
    )
    recipient = resolve_recipient_email(instructor_name, instructor_id)
    if not recipient:
        logger.warning(
            f"[MAIL] No recipient email found for teacher: {instructor_name or 'unknown'}"
        )
        return standard_response(
            False,
            "Faculty email not configured",
            error_code="EMAIL_NOT_CONFIGURED",
            status_code=422,
        )
    logger.info(f"[MAIL] Resolved recipient: {recipient}")

    # 5. Load attendance records - try DB first, then cache
    att = []
    if pg_db.is_db_available():
        att = pg_db.get_attendance_by_session_from_db(session_id)
        logger.info(f"[MAIL] Loaded {len(att)} records from DB")

    if not att:
        # Fallback to cache
        att = get_cached_attendance(session_id)
        logger.info(f"[MAIL] Loaded {len(att)} records from cache")

    if not att:
        # Fallback to JSON file
        for root, dirs, files in os.walk(REPORTS_DIR):
            for f in files:
                if f.endswith(".json") and session_id[:8] in f:
                    try:
                        with open(os.path.join(root, f), "r") as jf:
                            data = json.load(jf)
                            att = data.get("attendance", [])
                            logger.info(
                                f"[MAIL] Loaded {len(att)} records from JSON file"
                            )
                            break
                    except Exception as e:
                        logger.error(f"[MAIL] Failed to read attendance from JSON: {e}")
            if att:
                break

    # Resolve names
    names, _ = load_student_records()
    for rec in att:
        if not rec.get("name") or rec["name"] in ("Unknown", "Unknown Student"):
            rec["name"] = names.get(
                rec["roll_number"].strip().upper(), "Unknown Student"
            )

    logger.info(f"[MAIL] Total attendance records: {len(att)}")

    # 6. Use existing Excel file instead of regenerating
    # Find the existing Excel file for this session
    excel_path = None
    instructor_id = session.get("instructor_id") or session.get("teacher_id", "")
    dept = session.get("department", "")
    year = str(session.get("year", ""))
    section = session.get("section", "")

    if instructor_id and dept and year and section:
        search_path = os.path.join(REPORTS_DIR, instructor_id, dept, year, section)
        if os.path.exists(search_path):
            for f in os.listdir(search_path):
                if f.endswith(".xlsx") and session_id[:8] in f:
                    excel_path = os.path.join(search_path, f)
                    break

    xl_bytes = None
    if excel_path and os.path.exists(excel_path):
        logger.info(f"[MAIL ATTACH] session_id={session_id[:8]}")
        logger.info(f"[MAIL ATTACH] using existing export file: {excel_path}")
        with open(excel_path, "rb") as f:
            xl_bytes = f.read()
        logger.info(
            f"[MAIL ATTACH] file size: {len(xl_bytes)} bytes, matches download export: true"
        )
    else:
        # Fallback: generate in memory if file not found
        logger.warning(f"[MAIL ATTACH] Excel file not found, regenerating in memory")
        try:
            xl_bytes = generate_excel_bytes(session, att, names)
        except Exception as e:
            logger.error(
                f"[MAIL] Excel generation failed: {e}\n{traceback.format_exc()}"
            )
            return standard_response(
                False,
                "Failed to generate Excel attachment.",
                error_code="EXCEL_ERROR",
                status_code=500,
            )

    # 7. Send email
    try:
        send_attendance_email(session, att, recipient, xl_bytes)
        logger.info(f"[MAIL] Email sent successfully to {recipient}")
    except RuntimeError as e:
        # Config errors (mail disabled, password missing)
        logger.error(f"[MAIL] Config error: {e}")
        return standard_response(
            False, str(e), error_code="MAIL_CONFIG_ERROR", status_code=500
        )
    except Exception as e:
        logger.error(f"[MAIL] SMTP delivery failed: {e}\n{traceback.format_exc()}")
        return standard_response(
            False,
            f"Email delivery failed: {str(e)}",
            error_code="SMTP_ERROR",
            status_code=500,
        )

    # 8. Mark sent in DB (best effort — don't fail the response if this fails)
    try:
        if pg_db.is_db_available():
            pg_db.mark_mail_sent(session_id)
        # Also update cache
        cached = get_finalized_session(session_id)
        if cached:
            cached["mail_sent"] = True
            cached["mail_sent_at"] = datetime.now(LOCAL_TZ).isoformat()
            cache_finalized_session(session_id, cached)
        logger.info(f"[MAIL] Marked mail_sent for session: {session_id[:8]}")
    except Exception as e:
        logger.error(f"[MAIL] Could not mark mail_sent in DB: {e}")

    return standard_response(True, f"Email sent to {recipient}")


@app.get("/health")
async def health():
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────────────────────────────────────


@app.on_event("startup")
async def preflight():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    load_student_records()
    # Run DB migrations on every startup — safe, idempotent
    if pg_db.is_db_available():
        pg_db.run_migrations()
        logger.info("[STARTUP] DB migrations applied.")
    else:
        logger.warning("[STARTUP] DB not available — running in file-only mode.")
