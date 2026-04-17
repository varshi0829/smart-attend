"""
SmartAttend — Mail sending module for the Attendance Service.

Phase 2 scope:
  - resolve_recipient_email()  → TEMPORARY fallback mapping (Phase 5 will replace)
  - generate_excel_bytes()     → build Excel attachment in memory
  - send_attendance_email()    → send via SMTP using env-configured credentials

Phase 5 will replace resolve_recipient_email() with a real faculty email lookup
from the DB without changing the rest of this module.
"""

import re
import smtplib
import logging
from io import BytesIO
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Optional, List, Dict

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

from .config import (
    MAIL_ENABLED, SMTP_HOST, SMTP_PORT,
    SMTP_USERNAME, SMTP_PASSWORD,
    MAIL_FROM, MAIL_FROM_NAME,
    ATTENDANCE_TIMEZONE,
)

logger = logging.getLogger("Mailer")


# ─────────────────────────────────────────────────────────────────────────────
# TEMPORARY RECIPIENT MAPPING — Phase 5 will replace this entire block
# ─────────────────────────────────────────────────────────────────────────────
# For now only Murali Nath (in various normalised forms) has a mapped email.
# Any other instructor returns None, which causes a 422 "email not configured"
# error — this is intentional until Phase 5 populates real faculty emails.
#
# TO ADD MORE INSTRUCTORS TEMPORARILY: add entries here using the lowercase,
# punctuation-stripped form of the name as the key.
# ─────────────────────────────────────────────────────────────────────────────
_TEMP_FACULTY_EMAIL_MAP: Dict[str, str] = {
    # R S Murali Nath — various name formats that may appear after normalization
    "murali nath":           "adapasreevarshitha@gmail.com",  # TEMP
    "r s murali nath":       "adapasreevarshitha@gmail.com",  # TEMP
    "rs murali nath":        "adapasreevarshitha@gmail.com",  # TEMP
    "prof r s murali nath":  "adapasreevarshitha@gmail.com",  # TEMP
    "prof r s murali nath":  "adapasreevarshitha@gmail.com",  # TEMP (duplicate key, kept for reference)
    "prof murali nath":     "adapasreevarshitha@gmail.com",  # TEMP
}


def _normalize_name(name: str) -> str:
    """
    Normalize instructor name for matching.
    - lowercase
    - strip punctuation (including dots in initials like R.S. -> rs)
    - replace underscores/hyphens with spaces
    - collapse multiple spaces
    - remove title prefixes: prof, professor, dr, etc.
    """
    if not name:
        return ""
    
    # Step 1: lowercase
    norm = name.lower()
    
    # Step 2: replace underscores and hyphens with spaces
    norm = norm.replace('_', ' ').replace('-', ' ')
    
    # Step 3: remove all non-alphabetic characters except spaces
    norm = re.sub(r'[^a-z\s]', ' ', norm)
    
    # Step 4: collapse multiple spaces
    norm = re.sub(r'\s+', ' ', norm).strip()
    
    # Step 5: remove common title prefixes
    title_prefixes = ['prof', 'professor', 'dr', 'mr', 'mrs', 'ms']
    words = norm.split()
    filtered_words = [w for w in words if w not in title_prefixes]
    norm = ' '.join(filtered_words)
    
    # Step 6: final collapse of any extra spaces
    norm = re.sub(r'\s+', ' ', norm).strip()
    
    logger.info(f"[TEMP MAIL MAP] raw='{name}' normalized='{norm}'")
    return norm


def resolve_recipient_email(teacher_name: str, teacher_id: str) -> Optional[str]:
    """
    TEMPORARY (Phase 5 placeholder) — look up the instructor's email.

    Phase 5 will replace this with a DB query:
        SELECT email FROM teachers WHERE teacher_id = %s

    For now returns a mapped email only for Murali Nath.
    Returns None for any other instructor (triggers a 422 in the endpoint).
    
    Accepts teacher_name OR instructor_name from session data.
    """
    # Use teacher_name if provided, otherwise teacher_id may contain the name in some cases
    # But primarily we should check the session dict for instructor_name
    # The caller should pass the correct name in teacher_name parameter
    raw_name = teacher_name if teacher_name else ""
    
    # If teacher_name is empty, try to use a fallback (could be in teacher_id in some flows)
    # But primarily the session dict should have instructor_name
    if not raw_name:
        logger.warning(f"[TEMP MAIL MAP] No teacher_name provided, teacher_id='{teacher_id}'")
        # Try to use teacher_id as fallback (some systems store name in ID field)
        raw_name = teacher_id
    
    norm = _normalize_name(raw_name)
    
    # Try direct match first
    email = _TEMP_FACULTY_EMAIL_MAP.get(norm)
    
    # If no direct match, try partial matching for Murali Nath
    if not email:
        # Check if "murali nath" appears anywhere in the normalized name
        if "murali nath" in norm or "muralinath" in norm.replace(" ", ""):
            email = "adapasreevarshitha@gmail.com"
            logger.info(f"[TEMP MAIL MAP] Partial match for Murali Nath in '{norm}' -> {email}")
    
    if email:
        logger.info(f"[TEMP MAIL MAP] Matched '{raw_name}' (norm: '{norm}') -> {email}")
    else:
        logger.warning(
            f"[TEMP MAIL MAP] No email configured for '{raw_name}' (norm: '{norm}'). "
            "Phase 5 will add real faculty email data."
        )
    return email


# ─────────────────────────────────────────────────────────────────────────────
# Excel generation (in-memory, for email attachment)
# ─────────────────────────────────────────────────────────────────────────────

def generate_excel_bytes(session: dict, attendance_records: List[dict], names: Dict[str, str]) -> bytes:
    """
    Generate an Excel attendance report in memory and return the raw bytes.
    Used as the email attachment.

    session:            dict from get_session_by_id_from_db() or cached session
    attendance_records: list of {roll_number, name, timestamp} for present students
    names:              {roll_number: student_name} full class lookup (for absent list)
    """
    from zoneinfo import ZoneInfo
    IST = ZoneInfo(ATTENDANCE_TIMEZONE)

    start_dt = None
    if session.get('start_time'):
        try:
            start_dt = datetime.fromisoformat(session['start_time']).astimezone(IST)
        except Exception:
            pass

    # Use instructor_name field (from QR service) with teacher_name as fallback
    teacher_name = session.get('instructor_name') or session.get('teacher_name') or 'Faculty'
    dept    = session.get('department', '')
    year    = session.get('year', '')
    section = session.get('section', '')
    subject = session.get('subject', '')
    class_name = f"{dept}-{section}" if dept and section else (session.get('class_name') or 'Unknown Class')
    date_str = start_dt.strftime("%Y-%m-%d") if start_dt else "Unknown Date"

    # Compute counts from attendance records - this is the authoritative source
    present_set = {r['roll_number'].strip().upper() for r in attendance_records}
    present_count = len(present_set)
    
    # Get total students from session or compute from names (section-based)
    total_count = session.get('total_students', 0)
    if total_count == 0 and names:
        # Try to compute total from names - filter by class
        class_key = class_name.upper()
        total_count = sum(1 for s in names.values() if s.upper() == class_key)
    
    absent_count = max(0, total_count - present_count) if total_count > 0 else 0

    logger.info(f"[MAIL DATA] Generating Excel - session_id={session.get('session_id', 'unknown')[:8]}")
    logger.info(f"[MAIL DATA] source=finalized_current_session_payload")
    logger.info(f"[MAIL DATA] faculty='{teacher_name}'")
    logger.info(f"[MAIL DATA] subject='{subject}'")
    logger.info(f"[MAIL DATA] class='{class_name}'")
    logger.info(f"[MAIL_DATA] date='{date_str}'")
    logger.info(f"[MAIL DATA] counts present={present_count} total={total_count} absent={absent_count}")

    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"

    # Header row
    ws.append(["Subject", subject, "Class", class_name, "Date", date_str])
    # Use instructor_name for faculty
    ws.append(["Faculty", teacher_name, "Year", year, "Section", section])
    ws.append(["Present", present_count, "Total", total_count, "Absent", absent_count])
    ws.append([])
    ws.append(["S.No", "Roll Number", "Name", "Status", "Time"])

    # Bold header
    for col in range(1, 6):
        ws.cell(row=5, column=col).font = Font(bold=True)

    # Build time map for quick lookup
    time_map = {r['roll_number'].strip().upper(): r.get('timestamp', '') for r in attendance_records}

    # All students in the section (present + absent), sorted by roll number
    all_rolls = sorted(set(list(present_set) + list(names.keys())))

    row_num = 1
    for roll in all_rolls:
        is_present = roll in present_set
        ts = time_map.get(roll, '')
        time_display = ''
        if ts:
            try:
                t = datetime.fromisoformat(ts).astimezone(IST)
                time_display = t.strftime("%H:%M:%S")
            except Exception:
                time_display = str(ts)[-8:] if ts else ''

        ws.append([
            row_num,
            roll,
            names.get(roll, 'Unknown'),
            'Present' if is_present else 'Absent',
            time_display,
        ])
        row_num += 1

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Email sending
# ─────────────────────────────────────────────────────────────────────────────

def send_attendance_email(
    session: dict,
    attendance_records: List[dict],
    recipient_email: str,
    excel_bytes: bytes,
) -> None:
    """
    Build and send the attendance email via SMTP (STARTTLS).
    Raises RuntimeError if mail is disabled or credentials are missing.
    Raises smtplib.SMTPException (or subclasses) on delivery failure.

    session:            dict from get_session_by_id_from_db()
    attendance_records: list of present students
    recipient_email:    resolved from resolve_recipient_email()
    excel_bytes:        from generate_excel_bytes()
    """
    if not MAIL_ENABLED:
        raise RuntimeError("Mail is disabled. Set MAIL_ENABLED=true in attendance-service/.env")
    if not SMTP_PASSWORD:
        raise RuntimeError(
            "SMTP_PASSWORD is not set. Add it to attendance-service/.env and restart the service."
        )

    from zoneinfo import ZoneInfo
    IST = ZoneInfo(ATTENDANCE_TIMEZONE)

    # Format dates
    start_dt = end_dt = None
    if session.get('start_time'):
        try:
            start_dt = datetime.fromisoformat(session['start_time']).astimezone(IST)
        except Exception:
            pass
    if session.get('ended_at'):
        try:
            end_dt = datetime.fromisoformat(session['ended_at']).astimezone(IST)
        except Exception:
            pass

    date_str  = start_dt.strftime("%d %B %Y") if start_dt else "N/A"
    start_str = start_dt.strftime("%I:%M %p")  if start_dt else "N/A"
    end_str   = end_dt.strftime("%I:%M %p")    if end_dt   else "N/A"

    # Use instructor_name with teacher_name as fallback
    teacher_name = session.get('instructor_name') or session.get('teacher_name') or 'Faculty'
    subject_name = session.get('subject', 'N/A')
    dept         = session.get('department', 'N/A')
    year         = session.get('year', 'N/A')
    section      = session.get('section', 'N/A')
    semester     = session.get('semester') or 'N/A'
    
    # Compute counts from attendance records - authoritative source
    present_count = len(attendance_records)
    total_students = session.get('total_students', 0)
    
    # If total_students not in session, try to get from total_count field
    if total_students == 0:
        total_students = session.get('total_count', 0)
    
    # Calculate absent
    if total_students > 0:
        absent_count = max(0, total_students - present_count)
    else:
        absent_count = 0

    logger.info(f"[MAIL DATA] Email body - faculty='{teacher_name}', subject='{subject_name}', "
                f"class='{dept}-{section}', date='{date_str}', counts present={present_count} total={total_students} absent={absent_count}")

    # Short attendance preview (first 10 present students)
    preview_lines = [
        f"  {i+1:>2}. {r['roll_number']} — {r.get('name', 'Unknown')}"
        for i, r in enumerate(attendance_records[:10])
    ]
    if len(attendance_records) > 10:
        preview_lines.append(f"  ... and {len(attendance_records) - 10} more (see attachment)")
    preview_block = "\n".join(preview_lines) if preview_lines else "  (no students marked present)"

    body = f"""\
SmartAttend — Attendance Report
{'=' * 52}

Faculty    : {teacher_name}
Subject    : {subject_name}
Department : {dept}
Year       : {year}
Section    : {section}
Semester   : {semester}
Date       : {date_str}
Start Time : {start_str}
End Time   : {end_str}

Present    : {present_count}
Total      : {total_students}
Absent     : {absent_count}

Attendance Preview (present students):
{preview_block}

The full attendance list (including absent students) is attached as an Excel file.

—
Sent by SmartAttend | BVRITH
(This is an automated message — please do not reply directly to this email.)
"""

    # Build MIME message
    msg = MIMEMultipart()
    msg['From']    = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"
    msg['To']      = recipient_email
    msg['Subject'] = (
        f"Attendance — {subject_name} | "
        f"{dept} Y{year}-{section} | {date_str}"
    )

    msg.attach(MIMEText(body, 'plain'))

    # Attach Excel file
    xl_filename = (
        f"Attendance_{dept}_{year}_{section}_{date_str.replace(' ', '_')}.xlsx"
    )
    excel_part = MIMEApplication(excel_bytes, Name=xl_filename)
    excel_part['Content-Disposition'] = f'attachment; filename="{xl_filename}"'
    msg.attach(excel_part)

    logger.info(f"[MAILER] Connecting to {SMTP_HOST}:{SMTP_PORT}…")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.sendmail(MAIL_FROM, recipient_email, msg.as_string())

    logger.info(f"[MAILER] Email delivered to {recipient_email} for session {session.get('session_id')}")
