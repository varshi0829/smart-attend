#!/usr/bin/env python3
"""
build_faculty_assignments.py
============================
Derives teacher-specific academic assignments from:
  1. cse_course.csv        - course metadata (code → name, semester)
  2. teach _cse.csv        - teacher → course ownership
  3. INDIVIDUAL TIME TABLES 25-26 -I SEM 07-09-25.pdf - authoritative source for
                             faculty → class/year/section/subject mapping

Outputs:
  faculty_class_assignments.csv        (in same directory as this script)
  ../../frontend-instructor/faculty_assignments.json   (consumed by the instructor app)

Usage:
  python3 build_faculty_assignments.py

Requirements:
  - pdftotext (poppler-utils)  →  sudo apt install poppler-utils
  - Python 3.7+, no third-party libs needed
"""

import re
import csv
import json
import subprocess
import os
import sys
from datetime import date

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
COURSE_CSV = os.path.join(BASE_DIR, "cse_course.csv")
TEACH_CSV  = os.path.join(BASE_DIR, "teach _cse.csv")
PDF_PATH   = os.path.join(BASE_DIR, "INDIVIDUAL TIME TABLES 25-26 -I SEM  07-09-25.pdf")
OUT_CSV    = os.path.join(BASE_DIR, "faculty_class_assignments.csv")
# JSON goes into the instructor frontend so it can be served statically
OUT_JSON   = os.path.join(BASE_DIR, "..", "..", "..", "frontend-instructor", "faculty_assignments.json")

# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────
ROMAN_MAP = {"I": 1, "II": 2, "III": 3, "IV": 4}

# Accepted departments (add more as needed)
DEPT_PATTERN = r"(?:CSE|ECE|IT|EEE|MECH|CIVIL|AIML|AIDS|MLDS|MINOR|DSAI)"

# Regex to match a class identifier at the START of a field
# e.g. "IV CSE B", "II CSE A,B", "III ECE", "I CSE E,F"
CLASS_RE = re.compile(
    r"^(IV|III|II|I)\s+(" + DEPT_PATTERN + r")\s*([A-F](?:\s*,\s*[A-F])*)?$",
    re.IGNORECASE
)

# Subject code: e.g. CS701PC, EC511PE, MA402BS, *MC310
CODE_RE = re.compile(r"^\*?[A-Z]{2}[0-9]{3}[A-Z]{2}$")

# Acronym: all-caps, short, may contain space/slash/digits
# (positioned right after the subject code in the table row)
ACRONYM_RE = re.compile(r"^[A-Z][A-Z0-9/\s-]{0,20}$")


# ──────────────────────────────────────────────
# Step 1 – Load cse_course.csv
# ──────────────────────────────────────────────
def load_courses():
    """Return dict: code → {name, semester, year}"""
    courses = {}
    if not os.path.exists(COURSE_CSV):
        print(f"[WARN] cse_course.csv not found: {COURSE_CSV}")
        return courses
    with open(COURSE_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row.get("CourseId", "").strip()
            name = row.get("Course Name", "").strip()
            sem_str = row.get("Semester", "").strip()  # e.g. "Sem 3"
            sem_num = 0
            m = re.search(r"(\d+)", sem_str)
            if m:
                sem_num = int(m.group(1))
            year = ((sem_num - 1) // 2) + 1 if sem_num > 0 else 0
            if code:
                courses[code] = {"name": name, "semester": sem_num, "year": year}
    return courses


# ──────────────────────────────────────────────
# Step 2 – Load teach _cse.csv
# ──────────────────────────────────────────────
def load_teacher_courses():
    """Return dict: normalized_teacher_name → set of course codes"""
    mapping = {}
    if not os.path.exists(TEACH_CSV):
        print(f"[WARN] teach _cse.csv not found: {TEACH_CSV}")
        return mapping
    with open(TEACH_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            teacher = row.get("Teacher Name", "").strip()
            codes_str = row.get("Course ID", "").strip()
            if not teacher:
                continue
            norm = normalize_name(teacher)
            codes = {c.strip() for c in codes_str.split(";") if c.strip()}
            mapping.setdefault(norm, set()).update(codes)
    return mapping


# ──────────────────────────────────────────────
# Name normalization helpers
# ──────────────────────────────────────────────
def normalize_name(name: str) -> str:
    """Lowercase, remove all punctuation, collapse whitespace."""
    name = name.lower()
    name = re.sub(r"[^a-z\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def name_to_id(name: str) -> str:
    """Convert display name to a safe filesystem/URL-friendly id."""
    return normalize_name(name).replace(" ", "_")


# ──────────────────────────────────────────────
# Step 3 – Parse PDF
# ──────────────────────────────────────────────
def extract_pdf_text() -> str:
    """Run pdftotext -layout and return the full text."""
    if not os.path.exists(PDF_PATH):
        print(f"[ERROR] PDF not found: {PDF_PATH}")
        sys.exit(1)
    result = subprocess.run(
        ["pdftotext", "-layout", PDF_PATH, "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        print(f"[ERROR] pdftotext failed: {result.stderr}")
        sys.exit(1)
    return result.stdout


def split_fields(line: str):
    """Split a layout-text line into fields using 2+ spaces as delimiter."""
    return [f.strip() for f in re.split(r" {2,}", line.strip()) if f.strip()]


def classify_field(field: str):
    """
    Return a tuple (field_type, value) where field_type is one of:
      'class', 'code', 'acronym', 'name', 'number', 'other'
    """
    if not field:
        return "other", field

    # Pure number (S.No or hours)
    if re.match(r"^\d+$", field):
        return "number", field

    # Class identifier
    if CLASS_RE.match(field):
        return "class", field

    # Subject code
    if CODE_RE.match(field):
        return "code", field

    # Short ALL-CAPS string → potential acronym
    if ACRONYM_RE.match(field) and len(field) <= 25 and field == field.upper():
        return "acronym", field

    # Otherwise: subject name fragment or other text
    return "name", field


def parse_class_str(class_str: str):
    """
    Parse a class string like "IV CSE B", "II CSE A,B", "III ECE".
    Returns (year_int, dept_str, sections_list).
    sections_list is [] if no section is specified.
    """
    m = CLASS_RE.match(class_str.strip())
    if not m:
        return None, None, []
    roman = m.group(1).upper()
    dept  = m.group(2).upper()
    secs_raw = m.group(3) or ""
    year = ROMAN_MAP.get(roman, 0)
    sections = [s.strip().upper() for s in secs_raw.split(",") if s.strip()]
    return year, dept, sections


def parse_pdf_pages(text: str):
    """
    Parse the full pdftotext -layout output.
    Returns list of raw assignment dicts:
      {teacher_name, year, dept, section, code, acronym, raw_name, class_str}
    """
    raw_records = []
    pages = text.split("\f")

    for page in pages:
        lines = page.split("\n")

        # 1. Extract faculty name
        teacher_name = None
        for line in lines:
            m = re.search(r"Name of the Faculty:\s*(.+)", line)
            if m:
                teacher_name = m.group(1).strip()
                break
        if not teacher_name:
            continue

        # 2. Find table start (header row with "S. No" and "Class")
        table_start = None
        for i, line in enumerate(lines):
            if "S. No" in line and "Class" in line:
                table_start = i + 1
                break
        if table_start is None:
            continue

        # 3. Find table end ("Total Workload")
        table_end = len(lines)
        for i, line in enumerate(lines[table_start:], table_start):
            if "Total Workload" in line:
                table_end = i
                break

        # 4. Parse table lines
        # Each row that has a class field is one assignment.
        # Rows with only numbers (S.No / hours) are skipped.
        # Rows with only name text (continuation) are tracked to append names.
        current_class = None
        current_code  = None
        current_acronym = None
        current_name_parts = []

        def flush_record():
            nonlocal current_class, current_code, current_acronym, current_name_parts
            if current_class:
                year, dept, sections = parse_class_str(current_class)
                if year:
                    target_sections = sections if sections else [""]
                    for sec in target_sections:
                        raw_records.append({
                            "teacher_name": teacher_name,
                            "year": year,
                            "dept": dept,
                            "section": sec,
                            "code": current_code or "",
                            "acronym": current_acronym or "",
                            "raw_name": " ".join(current_name_parts).strip(),
                            "class_str": current_class,
                        })
            current_class = None
            current_code  = None
            current_acronym = None
            current_name_parts = []

        for line in lines[table_start:table_end]:
            if not line.strip():
                continue

            fields = split_fields(line)
            if not fields:
                continue

            # Classify each field
            classified = [classify_field(f) for f in fields]
            types = [c[0] for c in classified]

            # If this line has a class field, it starts a new assignment
            if "class" in types:
                flush_record()
                for ftype, fval in classified:
                    if ftype == "class":
                        current_class = fval
                    elif ftype == "code" and not current_code:
                        current_code = fval
                    elif ftype == "acronym" and not current_acronym:
                        current_acronym = fval
                    elif ftype == "name":
                        current_name_parts.append(fval)
                    # skip 'number' fields

            elif "code" in types and current_class:
                # Code on a new line (shouldn't happen in this PDF but handle it)
                for ftype, fval in classified:
                    if ftype == "code" and not current_code:
                        current_code = fval
                    elif ftype == "acronym" and not current_acronym:
                        current_acronym = fval
                    elif ftype == "name":
                        current_name_parts.append(fval)

            elif all(t in ("name", "other", "number") for t in types):
                # Possible name continuation – only accept non-numeric text
                for ftype, fval in classified:
                    if ftype == "name" and fval:
                        current_name_parts.append(fval)

        flush_record()

    return raw_records


# ──────────────────────────────────────────────
# Step 4 – Enrich and normalize
# ──────────────────────────────────────────────
def is_lab(code: str, acronym: str, name: str) -> bool:
    joined = f"{code} {acronym} {name}".upper()
    return "LAB" in joined


def derive_semester(year: int) -> int:
    """I-Semester mapping: year → odd semester."""
    return (year * 2) - 1


def build_assignments(raw_records, courses, teacher_courses):
    """
    Merge PDF raw records with course and teacher-course CSVs.
    Returns list of enriched assignment dicts.
    """
    enriched = []
    for rec in raw_records:
        code = rec["code"].lstrip("*")

        # Full subject name: prefer course CSV, then raw name from PDF, then acronym
        subject_name = ""
        course_year  = rec["year"]  # default to timetable year
        semester     = derive_semester(rec["year"])

        if code and code in courses:
            subject_name = courses[code]["name"]
            # If course CSV has semester info, use it (more authoritative)
            if courses[code]["semester"]:
                semester = courses[code]["semester"]
                course_year = ((semester - 1) // 2) + 1
        elif rec["raw_name"]:
            subject_name = rec["raw_name"]
        elif rec["acronym"]:
            subject_name = rec["acronym"]

        # Source confidence
        if code and code in courses:
            confidence = "high"
            source_notes = "derived from timetable + course CSV"
        elif code:
            confidence = "medium"
            source_notes = "code from timetable, not in course CSV"
        else:
            confidence = "low"
            source_notes = "no code found in timetable"

        enriched.append({
            "teacher_name": rec["teacher_name"],
            "teacher_name_normalized": normalize_name(rec["teacher_name"]),
            "department": rec["dept"],
            "year": str(rec["year"]),
            "semester": str(semester),
            "section": rec["section"],
            "subject_code": code,
            "subject_acronym": rec["acronym"],
            "subject_name": subject_name,
            "class_type": "Lab" if is_lab(code, rec["acronym"], rec["raw_name"]) else "Theory",
            "class_str": rec["class_str"],
            "source_confidence": confidence,
            "source_notes": source_notes,
        })
    return enriched


# ──────────────────────────────────────────────
# Step 5 – Write CSV
# ──────────────────────────────────────────────
CSV_COLUMNS = [
    "teacher_name", "teacher_name_normalized", "department", "year", "semester",
    "section", "subject_code", "subject_acronym", "subject_name",
    "class_type", "class_str", "source_confidence", "source_notes",
]

def write_csv(records):
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for rec in records:
            writer.writerow({k: rec.get(k, "") for k in CSV_COLUMNS})
    print(f"[OK] CSV written: {OUT_CSV}  ({len(records)} rows)")


# ──────────────────────────────────────────────
# Step 6 – Write JSON (consumed by frontend)
# ──────────────────────────────────────────────
def write_json(records):
    """
    Output structure:
    {
      "generated": "YYYY-MM-DD",
      "faculty": {
        "dr s l aruna rao": {
          "id": "dr_s_l_aruna_rao",
          "display_name": "Dr. S L Aruna Rao",
          "assignments": [ {year, semester, department, section, ...}, ... ]
        },
        ...
      }
    }
    """
    faculty_map = {}

    for rec in records:
        key = rec["teacher_name_normalized"]
        if key not in faculty_map:
            faculty_map[key] = {
                "id": name_to_id(rec["teacher_name"]),
                "display_name": rec["teacher_name"],
                "assignments": []
            }

        # Only include assignments that have a section (so sessions can be created)
        if not rec["section"]:
            continue  # skip "all-section" / unknown-section entries

        assignment = {
            "year": rec["year"],
            "semester": rec["semester"],
            "department": rec["department"],
            "section": rec["section"],
            "subject_code": rec["subject_code"],
            "subject_acronym": rec["subject_acronym"],
            "subject_name": rec["subject_name"],
            "class_type": rec["class_type"],
        }

        # Deduplicate exact records
        if assignment not in faculty_map[key]["assignments"]:
            faculty_map[key]["assignments"].append(assignment)

    output = {
        "generated": str(date.today()),
        "source": "INDIVIDUAL TIME TABLES 25-26 -I SEM 07-09-25.pdf + cse_course.csv + teach _cse.csv",
        "faculty": faculty_map,
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    total_assignments = sum(len(v["assignments"]) for v in faculty_map.values())
    print(f"[OK] JSON written: {OUT_JSON}")
    print(f"     {len(faculty_map)} faculty members, {total_assignments} assignment entries")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    print("=== SmartAttend Faculty Assignment Deriver ===\n")

    print("[1/4] Loading cse_course.csv ...")
    courses = load_courses()
    print(f"      {len(courses)} courses loaded")

    print("[2/4] Loading teach _cse.csv ...")
    teacher_courses = load_teacher_courses()
    print(f"      {len(teacher_courses)} teachers loaded")

    print("[3/4] Parsing timetable PDF ...")
    pdf_text = extract_pdf_text()
    raw_records = parse_pdf_pages(pdf_text)
    print(f"      {len(raw_records)} raw class-assignment records extracted from PDF")

    print("[4/4] Enriching and writing outputs ...")
    records = build_assignments(raw_records, courses, teacher_courses)
    write_csv(records)
    write_json(records)

    print("\n=== Done ===")
    print(f"Run the instructor app and log in with any faculty name from the timetable.")
    print(f"Example:  'Aruna Rao'  or  'Dr. S L Aruna Rao'")


if __name__ == "__main__":
    main()