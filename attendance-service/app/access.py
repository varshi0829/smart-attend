import json
import os
from functools import lru_cache

from . import db as pg_db

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ACCESS_CONTROL_PATH = os.path.join(ROOT_DIR, "attendance-service", "access_control.json")
FACULTY_ASSIGNMENTS_PATH = os.path.join(ROOT_DIR, "frontend-instructor", "faculty_assignments.json")


def normalize_name(name: str) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in (name or "")).split())


def normalize_role(role: str) -> str:
    role = (role or "faculty").strip().lower()
    if role == "instructor":
        return "faculty"
    return role


def normalize_assignment(assignment: dict) -> dict:
    return {
        "department": (assignment.get("department") or "").strip().upper(),
        "year": str(assignment.get("year") or "").strip(),
        "section": (assignment.get("section") or "").strip().upper(),
        "subject": assignment.get("subject") or assignment.get("subject_name") or assignment.get("subject_acronym") or "",
        "subject_code": assignment.get("subject_code") or assignment.get("course_code") or "",
        "class_type": assignment.get("class_type") or "",
    }


@lru_cache(maxsize=1)
def load_access_control():
    if not os.path.exists(ACCESS_CONTROL_PATH):
        return {"teachers": {}, "students": {}}

    try:
        with open(ACCESS_CONTROL_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {
                "teachers": data.get("teachers", {}) or {},
                "students": data.get("students", {}) or {},
            }
    except Exception:
        return {"teachers": {}, "students": {}}


@lru_cache(maxsize=1)
def load_faculty_assignments():
    if not os.path.exists(FACULTY_ASSIGNMENTS_PATH):
        return {"faculty": {}}

    try:
        with open(FACULTY_ASSIGNMENTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"faculty": {}}


def _teacher_override(actor_id: str = "", actor_name: str = "") -> dict:
    overrides = load_access_control().get("teachers", {})
    actor_id = (actor_id or "").strip()
    actor_name = normalize_name(actor_name)

    if actor_id and actor_id in overrides:
        return overrides[actor_id]
    if actor_name and actor_name in overrides:
        return overrides[actor_name]
    return {}


def _student_override(roll_number: str = "") -> dict:
    return load_access_control().get("students", {}).get((roll_number or "").strip().upper(), {})


def get_teacher_assignments(actor_id: str = "", actor_name: str = ""):
    assignments = []

    if actor_id and pg_db.is_db_available():
        assignments = pg_db.get_teacher_assignments(actor_id) or []

    if not assignments:
        faculty_data = load_faculty_assignments().get("faculty", {})
        if actor_name:
            teacher = faculty_data.get(normalize_name(actor_name))
            if teacher:
                assignments = teacher.get("assignments", [])
        if not assignments and actor_id:
            for teacher in faculty_data.values():
                if teacher.get("id") == actor_id:
                    assignments = teacher.get("assignments", [])
                    break

    return [normalize_assignment(a) for a in assignments]


def get_access_context(actor_id: str = "", actor_name: str = "", actor_role: str = "", student_roll_number: str = "") -> dict:
    role = normalize_role(actor_role)
    student_roll_number = (student_roll_number or "").strip().upper()

    if role == "student" or student_roll_number:
        return {
            "role": "student",
            "actor_id": "",
            "actor_name": "",
            "department": (_student_override(student_roll_number).get("department") or "").strip().upper(),
            "student_roll_number": student_roll_number,
            "assignments": [],
            "class_teacher_assignments": [],
            "is_class_teacher": False,
        }

    teacher = pg_db.get_teacher_by_identifier(actor_id=actor_id, name=actor_name) if pg_db.is_db_available() else None
    override = _teacher_override(actor_id=actor_id, actor_name=actor_name)

    resolved_role = normalize_role(override.get("role") or (teacher or {}).get("role") or role or "faculty")
    resolved_actor_id = (override.get("id") or (teacher or {}).get("id") or actor_id or "").strip()
    resolved_actor_name = (override.get("name") or (teacher or {}).get("name") or actor_name or "").strip()
    assignments = get_teacher_assignments(resolved_actor_id, resolved_actor_name)
    class_teacher_assignments = [normalize_assignment(a) for a in override.get("class_teacher_assignments", [])]

    return {
        "role": resolved_role,
        "actor_id": resolved_actor_id,
        "actor_name": resolved_actor_name,
        "department": (override.get("department") or (teacher or {}).get("department") or "").strip().upper(),
        "student_roll_number": "",
        "assignments": assignments,
        "class_teacher_assignments": class_teacher_assignments,
        "is_class_teacher": bool(override.get("is_class_teacher")) or bool(class_teacher_assignments),
    }


def assignment_matches(assignment: dict, department: str, year: str, section: str) -> bool:
    year = str(year or "").strip()
    section = (section or "").strip().upper()
    return (
        assignment.get("department", "").upper() == (department or "").upper()
        and (not year or str(assignment.get("year", "")).strip() == year)
        and (not section or assignment.get("section", "").upper() == section)
    )


def can_access_class_scope(ctx: dict, department: str, year: str, section: str, instructor_id: str = "", allow_faculty_assignment_match: bool = False) -> bool:
    role = normalize_role(ctx.get("role"))
    department = (department or "").strip().upper()
    year = str(year or "").strip()
    section = (section or "").strip().upper()
    instructor_id = (instructor_id or "").strip()

    if role == "principal":
        return True
    if role == "hod":
        return department == (ctx.get("department") or "").strip().upper()
    if role == "student":
        return False
    if ctx.get("is_class_teacher"):
        if any(assignment_matches(a, department, year, section) for a in ctx.get("class_teacher_assignments", [])):
            return True
    if instructor_id and instructor_id == ctx.get("actor_id"):
        return True
    if role == "faculty" and allow_faculty_assignment_match:
        return any(assignment_matches(a, department, year, section) for a in ctx.get("assignments", []))
    return False


def student_belongs_to_scope(ctx: dict, roll_number: str, section_code: str) -> bool:
    role = normalize_role(ctx.get("role"))
    roll_number = (roll_number or "").strip().upper()
    section_code = (section_code or "").strip().upper()
    department, _, section = section_code.partition("-")

    if role == "principal":
        return True
    if role == "student":
        return roll_number == (ctx.get("student_roll_number") or "").strip().upper()
    if role == "hod":
        return department == (ctx.get("department") or "").strip().upper()
    if ctx.get("is_class_teacher"):
        return any(
            a.get("department", "").upper() == department and a.get("section", "").upper() == section
            for a in ctx.get("class_teacher_assignments", [])
        )
    return False


def filter_assignments_for_context(ctx: dict, assignments: list) -> list:
    role = normalize_role(ctx.get("role"))
    if role == "principal":
        return assignments
    if role == "hod":
        dept = (ctx.get("department") or "").strip().upper()
        return [a for a in assignments if (a.get("department") or a.get("teacher_dept") or "").strip().upper() == dept]
    return assignments
