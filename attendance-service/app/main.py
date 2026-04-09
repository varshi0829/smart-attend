import httpx
import time
import logging
import os
import csv
import json
import traceback
from datetime import datetime, timezone
from typing import List, Dict, Optional
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from .responses import standard_response
from .integrations import verify_face, verify_qr, verify_grant, consume_grant
from .storage import db
from .config import FACE_SERVICE_URL, QR_SERVICE_URL, ATTENDANCE_TIMEZONE, INTERNAL_TLS_VERIFY, REPORTS_DIR

app = FastAPI(title="SmartAttend Attendance Orchestrator")
STUDENT_CACHE = None

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Orchestrator")

def load_student_records():
    global STUDENT_CACHE
    if STUDENT_CACHE is not None: return STUDENT_CACHE['names'], STUDENT_CACHE['sections']
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "backend", "students.csv")
    roll_to_name, roll_to_sec = {}, {}
    if not os.path.exists(csv_path):
        logger.error(f"CRITICAL: students.csv not found at {csv_path}")
        return {}, {}
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                r = row.get("rollnumber", "").strip().upper()
                if not r: continue
                roll_to_name[r] = row.get("name", "").strip()
                roll_to_sec[r] = row.get("section", "").strip().upper()
        STUDENT_CACHE = {'names': roll_to_name, 'sections': roll_to_sec}
        logger.info(f"SUCCESS: Loaded {len(roll_to_name)} students from CSV.")
    except Exception as e: 
        logger.error(f"CSV load failed: {e}")
    return roll_to_name, roll_to_sec

async def get_session_meta(sid: str):
    async with httpx.AsyncClient(verify=INTERNAL_TLS_VERIFY) as client:
        try:
            res = await client.get(f"{QR_SERVICE_URL}/session/{sid}", timeout=5.0)
            return res.json().get("data") if res.status_code == 200 else None
        except Exception as e:
            logger.error(f"Failed to fetch session meta for {sid}: {e}")
            return None

@app.post("/attendance/mark")
async def mark_attendance(roll_number: str = Form(...), grant_id: str = Form(...), session_id: str = Form(...), image: UploadFile = File(...)):
    roll_no = roll_number.strip().upper()
    
    # 1. Eligibility Check
    meta = await get_session_meta(session_id)
    if not meta: return standard_response(False, "Session not found", status_code=404)
    
    names, sections = load_student_records()
    if roll_no not in sections: return standard_response(False, "Student record not found", status_code=404)
    
    if sections[roll_no] != meta.get("class_name"):
        return standard_response(False, f"You belong to {sections[roll_no]}, but this session is for {meta['class_name']}", error_code="STUDENT_NOT_IN_SESSION_CLASS", status_code=403)

    # 2. Grant Verify
    g_res, g_status = await verify_grant(grant_id, roll_no, session_id)
    if g_status != 200: return standard_response(False, g_res.get("message"), error_code=g_res.get("error_code"), status_code=g_status)

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
                r_resp = await client.post(f"{QR_SERVICE_URL}/session/increment-retry", json={"grant_id": grant_id}, timeout=5.0)
                retry_count = r_resp.json().get("data", {}).get("retry_count", 0)
                if retry_count >= 3:
                    msg = "Face verification failed 3 times. This QR grant is now invalid. Please re-scan."
                    error_code = "GRANT_RETRY_LIMIT_REACHED"
        except Exception as e:
            logger.error(f"[PIPELINE] Failed to increment retry count: {e}")

        db.set_last_attempt(roll_no, "FAILED_FACE", {"error_code": error_code, "msg": msg})
        return standard_response(False, msg, error_code=error_code, status_code=f_status if f_status < 500 else 503)

    # 4. Atomic Save
    record, err = db.mark_attendance_atomic(roll_no, session_id, meta['instructor_id'], f_res.get("confidence", 0.0))
    if err: return standard_response(False, "Attendance already marked", error_code=err, status_code=400)
    
    await consume_grant(grant_id)
    return standard_response(True, "Success", data=record)

async def generate_excel_task(session_id: str):
    logger.info(f"[REPORT] Starting report generation for session: {session_id}")
    try:
        meta = await get_session_meta(session_id)
        if not meta: 
            logger.error(f"[REPORT] Meta not found for {session_id}")
            return
        
        from zoneinfo import ZoneInfo
        IST = ZoneInfo(ATTENDANCE_TIMEZONE)
        start_dt = datetime.fromisoformat(meta['start_time']).astimezone(IST)
        
        # Path: reports/inst_id/dept/year/section/
        class_dir = os.path.join(REPORTS_DIR, meta['instructor_id'], meta['department'], meta['year'], meta['section'])
        os.makedirs(class_dir, exist_ok=True)
        
        records = {r['roll_number']: r for r in db.get_by_session(session_id)}
        names, sections = load_student_records()
        target_students = [r for r in sections if sections[r] == meta['class_name']]
        
        wb = Workbook()
        ws = wb.active
        ws.append(["Subject", meta['subject'], "Class", meta['class_name'], "Date", start_dt.strftime("%Y-%m-%d")])
        ws.append(["S.No", "Roll Number", "Name", "Status", "Time"])
        
        for i, roll in enumerate(sorted(target_students), 1):
            is_p = roll in records
            ws.append([i, roll, names.get(roll, "Unknown"), "Present" if is_p else "Absent", records[roll]['timestamp'] if is_p else ""])
        
        filename = f"{start_dt.strftime('%H%M')}_{session_id[:8]}.xlsx"
        fpath = os.path.join(class_dir, filename)
        wb.save(fpath)
        logger.info(f"[REPORT] Excel saved: {fpath}")
        
        # Enrich records with names for the JSON viewer mirror
        enriched_attendance = []
        for roll, rec in records.items():
            normalized_roll = roll.strip().upper()
            rec_copy = rec.copy()
            rec_copy['name'] = names.get(normalized_roll, "Unknown Student")
            enriched_attendance.append(rec_copy)

        # Save JSON Mirror for high-speed in-app viewing
        with open(fpath.replace(".xlsx", ".json"), "w") as jf:
            json.dump({"meta": meta, "attendance": enriched_attendance}, jf)
        logger.info(f"[REPORT] JSON mirror saved with {len(enriched_attendance)} enriched records.")

    except Exception as e:
        logger.error(f"[REPORT] Generation failed: {e}\n{traceback.format_exc()}")

@app.post("/attendance/session/{session_id}/generate-report")
async def trigger_report(session_id: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(generate_excel_task, session_id)
    return standard_response(True, "Started")

@app.get("/reports/list")
async def list_reports(instructor_id: str, dept: str, year: str, sec: str):
    path = os.path.join(REPORTS_DIR, instructor_id, dept, year, sec)
    if not os.path.exists(path): return standard_response(True, "No reports", [])
    
    names, _ = load_student_records()
    files = [f for f in os.listdir(path) if f.endswith(".json")]
    results = []
    
    for f in files:
        try:
            with open(os.path.join(path, f), "r") as jf:
                data = json.load(jf)
                # DYNAMIC FALLBACK: Resolve names if missing or N/A
                for record in data.get("attendance", []):
                    roll = record.get("roll_number", "").strip().upper()
                    if roll and (not record.get("name") or record.get("name") == "N/A"):
                        record["name"] = names.get(roll, "Unknown Student")
                results.append(data)
        except Exception as e:
            logger.error(f"Error reading report {f}: {e}")
            
    return standard_response(True, "Found", results)

@app.get("/reports/download")
async def download_report(instructor_id: str, dept: str, year: str, sec: str, filename: str):
    fpath = os.path.join(REPORTS_DIR, instructor_id, dept, year, sec, filename)
    if os.path.exists(fpath): return FileResponse(fpath)
    raise HTTPException(status_code=404)

@app.on_event("startup")
async def preflight(): 
    os.makedirs(REPORTS_DIR, exist_ok=True)
    load_student_records()

@app.get("/attendance/session/{session_id}")
async def get_session_history(session_id: str):
    records = db.get_by_session(session_id)
    names, _ = load_student_records()
    return standard_response(True, "History", [{"roll_number": r['roll_number'], "name": names.get(r['roll_number'].strip().upper(), "Unknown"), "timestamp": r['timestamp']} for r in records])

@app.get("/attendance/class-list/{class_name}")
async def get_class_list(class_name: str):
    names, sections = load_student_records()
    target = class_name.upper().strip()
    students = [{"roll_number": r, "name": names[r]} for r in sections if sections[r] == target]
    return standard_response(True, f"Found {len(students)} students", students)

@app.get("/health")
async def health(): return {"status": "ok"}
