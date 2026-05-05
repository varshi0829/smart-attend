"""
SmartAttend — Mail sending module for the Attendance Service.

Phase 2 scope:
  - resolve_recipient_email()  → TEMPORARY fallback mapping (Phase 5 will replace)
  - generate_excel_bytes()     → build Excel attachment in memory
  - send_attendance_email()    → send via SMTP using env-configured credentials

Phase 5 uses the provided faculty JSON for recipient lookup and keeps the
resolver shape ready for future identity/OAuth mapping.
"""

import re
import json
import smtplib
import logging
from io import BytesIO
from pathlib import Path
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from functools import lru_cache
from typing import Optional, List, Dict, Any

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

from .config import (
    MAIL_ENABLED,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_PASSWORD,
    MAIL_FROM,
    MAIL_FROM_NAME,
    ATTENDANCE_TIMEZONE,
)

logger = logging.getLogger("Mailer")


# ─────────────────────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parents[2]
_FACULTY_DATA_PATHS = [
    _BASE_DIR / "frontend-instructor" / "faculty_assignments.json",
    _BASE_DIR / "Faculty" / "frontend-instructor" / "faculty_assignments.json",
]
_MURALI_OVERRIDE_EMAIL = "adapasreevarshitha@gmail.com"
_MURALI_OVERRIDE_KEYS = {
    "murali nath",
    "r s murali nath",
    "rs murali nath",
    "prof r s murali nath",
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
    norm = norm.replace("_", " ").replace("-", " ")

    # Step 3: remove all non-alphabetic characters except spaces
    norm = re.sub(r"[^a-z\s]", " ", norm)

    # Step 4: collapse multiple spaces
    norm = re.sub(r"\s+", " ", norm).strip()

    # Step 5: remove common title prefixes
    title_prefixes = ["prof", "professor", "dr", "mr", "mrs", "ms"]
    words = norm.split()
    filtered_words = [w for w in words if w not in title_prefixes]
    norm = " ".join(filtered_words)

    # Step 6: final collapse of any extra spaces
    norm = re.sub(r"\s+", " ", norm).strip()

    logger.info(f"[FACULTY MAP] raw='{name}' normalized='{norm}'")
    return norm


@lru_cache(maxsize=1)
def _load_faculty_index() -> Dict[str, Dict[str, Any]]:
    """Load faculty records from the provided JSON source(s)."""
    records_by_id: Dict[str, Dict[str, Any]] = {}

    for path in _FACULTY_DATA_PATHS:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception as exc:
            logger.warning(f"[FACULTY MAP] Failed to read {path}: {exc}")
            continue

        for raw_key, raw_value in payload.get("faculty", {}).items():
            if not isinstance(raw_value, dict):
                continue

            record_key = _normalize_name(raw_value.get("id") or raw_key)
            merged = dict(records_by_id.get(record_key, {}))

            for field, value in raw_value.items():
                if field == "email":
                    if value:
                        merged[field] = str(value).strip()
                elif value not in (None, "", [], {}):
                    merged[field] = value

            merged.setdefault("id", raw_value.get("id") or record_key)
            merged.setdefault("display_name", raw_value.get("display_name") or raw_key)
            merged.setdefault("assignments", raw_value.get("assignments", []))

            records_by_id[record_key] = merged

    return records_by_id


def _find_faculty_record(
    teacher_name: str = "", teacher_id: str = ""
) -> Optional[Dict[str, Any]]:
    index = _load_faculty_index()
    if not index:
        return None

    teacher_name_norm = _normalize_name(teacher_name)
    teacher_id_norm = _normalize_name(teacher_id)

    if (
        teacher_name_norm in _MURALI_OVERRIDE_KEYS
        or teacher_id_norm in _MURALI_OVERRIDE_KEYS
    ):
        return {
            "id": teacher_id or teacher_name or "murali_nath_testing",
            "display_name": teacher_name or teacher_id or "Prof. R S Murali Nath",
            "email": _MURALI_OVERRIDE_EMAIL,
            "assignments": [],
            "override": True,
        }

    for candidate in (teacher_id_norm, teacher_name_norm):
        if candidate and candidate in index:
            return index[candidate]

    # Fallback: match by word overlap so login/display-name variants still resolve.
    search_tokens = [t for t in teacher_name_norm.split() if len(t) >= 2]
    if not search_tokens:
        search_tokens = [t for t in teacher_id_norm.split() if len(t) >= 2]

    best_record = None
    best_score = 0.0
    for record in index.values():
        needles = [
            _normalize_name(record.get("id", "")),
            _normalize_name(record.get("display_name", "")),
        ]
        haystack = " ".join(needles)
        hits = sum(1 for token in search_tokens if token in haystack)
        score = hits / len(search_tokens) if search_tokens else 0.0
        if score > best_score:
            best_score = score
            best_record = record

    return best_record if best_score >= 0.5 else None


def lookup_faculty_details(
    teacher_name: str = "",
    teacher_id: str = "",
    department: str = "",
    year: str = "",
    section: str = "",
    subject: str = "",
) -> Dict[str, Any]:
    """Resolve faculty record, email, and matching assignment."""
    record = _find_faculty_record(teacher_name, teacher_id)
    if not record:
        return {"record": None, "assignment": None, "email": None}

    assignments = record.get("assignments") or []
    selected_assignment = None
    subject_norm = _normalize_name(subject)

    for assignment in assignments:
        if (
            department
            and str(assignment.get("department", "")).upper() != str(department).upper()
        ):
            continue
        if year and str(assignment.get("year", "")) != str(year):
            continue
        if (
            section
            and str(assignment.get("section", "")).upper() != str(section).upper()
        ):
            continue

        if subject_norm:
            candidates = [
                _normalize_name(assignment.get("subject_name", "")),
                _normalize_name(assignment.get("subject_code", "")),
                _normalize_name(assignment.get("subject_acronym", "")),
            ]
            if not any(
                subject_norm == candidate
                or subject_norm in candidate
                or candidate in subject_norm
                for candidate in candidates
                if candidate
            ):
                continue

        selected_assignment = assignment
        break

    if not selected_assignment and assignments:
        selected_assignment = assignments[0]

    return {
        "record": record,
        "assignment": selected_assignment,
        "email": (record.get("email") or "").strip() or None,
    }


def resolve_recipient_email(teacher_name: str, teacher_id: str) -> Optional[str]:
    """Resolve the recipient email for Send Mail."""
    details = lookup_faculty_details(teacher_name=teacher_name, teacher_id=teacher_id)
    email = details.get("email")
    if email:
        logger.info(f"[FACULTY MAP] Matched '{teacher_name or teacher_id}' -> {email}")
        return email

    logger.warning(
        f"[FACULTY MAP] No email configured for '{teacher_name or teacher_id}'."
    )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Excel generation (in-memory, for email attachment)
# ─────────────────────────────────────────────────────────────────────────────


def generate_excel_bytes(
    session: dict, attendance_records: List[dict], names: Dict[str, str]
) -> bytes:
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
    if session.get("start_time"):
        try:
            start_dt = datetime.fromisoformat(session["start_time"]).astimezone(IST)
        except Exception:
            pass

    # Use instructor_name field (from QR service) with teacher_name as fallback
    teacher_name = (
        session.get("instructor_name") or session.get("teacher_name") or "Faculty"
    )
    dept = session.get("department", "")
    year = session.get("year", "")
    section = session.get("section", "")
    subject = session.get("subject", "")
    class_name = (
        f"{dept}-{section}"
        if dept and section
        else (session.get("class_name") or "Unknown Class")
    )
    date_str = start_dt.strftime("%Y-%m-%d") if start_dt else "Unknown Date"

    # Compute counts from attendance records - this is the authoritative source
    present_set = {r["roll_number"].strip().upper() for r in attendance_records}
    present_count = len(present_set)

    # Get total students from session or compute from names (section-based)
    total_count = session.get("total_students", 0)
    if total_count == 0 and names:
        # Try to compute total from names - filter by class
        class_key = class_name.upper()
        total_count = sum(1 for s in names.values() if s.upper() == class_key)

    absent_count = max(0, total_count - present_count) if total_count > 0 else 0

    logger.info(
        f"[MAIL DATA] Generating Excel - session_id={session.get('session_id', 'unknown')[:8]}"
    )
    logger.info(f"[MAIL DATA] source=finalized_current_session_payload")
    logger.info(f"[MAIL DATA] faculty='{teacher_name}'")
    logger.info(f"[MAIL DATA] subject='{subject}'")
    logger.info(f"[MAIL DATA] class='{class_name}'")
    logger.info(f"[MAIL_DATA] date='{date_str}'")
    logger.info(
        f"[MAIL DATA] counts present={present_count} total={total_count} absent={absent_count}"
    )

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
    time_map = {
        r["roll_number"].strip().upper(): r.get("timestamp", "")
        for r in attendance_records
    }

    # All students in the section (present + absent), sorted by roll number
    all_rolls = sorted(set(list(present_set) + list(names.keys())))

    row_num = 1
    for roll in all_rolls:
        is_present = roll in present_set
        ts = time_map.get(roll, "")
        time_display = ""
        if ts:
            try:
                t = datetime.fromisoformat(ts).astimezone(IST)
                time_display = t.strftime("%H:%M:%S")
            except Exception:
                time_display = str(ts)[-8:] if ts else ""

        ws.append(
            [
                row_num,
                roll,
                names.get(roll, "Unknown"),
                "Present" if is_present else "Absent",
                time_display,
            ]
        )
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
        raise RuntimeError(
            "Mail is disabled. Set MAIL_ENABLED=true in attendance-service/.env"
        )
    if not SMTP_PASSWORD:
        raise RuntimeError(
            "SMTP_PASSWORD is not set. Add it to attendance-service/.env and restart the service."
        )

    from zoneinfo import ZoneInfo

    IST = ZoneInfo(ATTENDANCE_TIMEZONE)

    # Format dates
    start_dt = end_dt = None
    if session.get("start_time"):
        try:
            start_dt = datetime.fromisoformat(session["start_time"]).astimezone(IST)
        except Exception:
            pass
    if session.get("ended_at"):
        try:
            end_dt = datetime.fromisoformat(session["ended_at"]).astimezone(IST)
        except Exception:
            pass

    date_str = start_dt.strftime("%d %B %Y") if start_dt else "N/A"
    start_str = start_dt.strftime("%I:%M %p") if start_dt else "N/A"
    end_str = end_dt.strftime("%I:%M %p") if end_dt else "N/A"

    # Use instructor_name with teacher_name as fallback
    teacher_name = (
        session.get("instructor_name") or session.get("teacher_name") or "Faculty"
    )
    subject_name = session.get("subject", "N/A")
    dept = session.get("department", "N/A")
    year = session.get("year", "N/A")
    section = session.get("section", "N/A")
    semester = session.get("semester") or "N/A"

    # Compute counts from attendance records - authoritative source
    present_count = len(attendance_records)
    total_students = session.get("total_students", 0)

    # If total_students not in session, try to get from total_count field
    if total_students == 0:
        total_students = session.get("total_count", 0)

    # Calculate absent
    if total_students > 0:
        absent_count = max(0, total_students - present_count)
    else:
        absent_count = 0

    logger.info(
        f"[MAIL DATA] Email body - faculty='{teacher_name}', subject='{subject_name}', "
        f"class='{dept}-{section}', date='{date_str}', counts present={present_count} total={total_students} absent={absent_count}"
    )

    # Short attendance preview (first 10 present students)
    preview_lines = [
        f"  {i + 1:>2}. {r['roll_number']} — {r.get('name', 'Unknown')}"
        for i, r in enumerate(attendance_records[:10])
    ]
    if len(attendance_records) > 10:
        preview_lines.append(
            f"  ... and {len(attendance_records) - 10} more (see attachment)"
        )
    preview_block = (
        "\n".join(preview_lines) if preview_lines else "  (no students marked present)"
    )

    body = f"""\
SmartAttend — Attendance Report
{"=" * 52}

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
    msg["From"] = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"
    msg["To"] = recipient_email
    msg["Subject"] = (
        f"Attendance — {subject_name} | {dept} Y{year}-{section} | {date_str}"
    )

    msg.attach(MIMEText(body, "plain"))

    # Attach Excel file
    xl_filename = (
        f"Attendance_{dept}_{year}_{section}_{date_str.replace(' ', '_')}.xlsx"
    )
    excel_part = MIMEApplication(excel_bytes, Name=xl_filename)
    excel_part["Content-Disposition"] = f'attachment; filename="{xl_filename}"'
    msg.attach(excel_part)

    logger.info(f"[MAILER] Connecting to {SMTP_HOST}:{SMTP_PORT}…")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.sendmail(MAIL_FROM, recipient_email, msg.as_string())

    logger.info(
        f"[MAILER] Email delivered to {recipient_email} for session {session.get('session_id')}"
    )
