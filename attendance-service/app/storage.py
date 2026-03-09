import uuid
import threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Tuple
from .config import ATTENDANCE_TIMEZONE

LOCAL_TZ = ZoneInfo(ATTENDANCE_TIMEZONE)

class AttendanceStore:
    def __init__(self):
        # {session_id: {roll_number: record}}
        self.records: Dict[str, Dict[str, dict]] = {}
        # {date_str: {roll_number: bool}}
        self.daily_registry: Dict[str, Dict[str, bool]] = {}
        # Simple history list
        self.history: List[dict] = []
        # Last processed attempt (debug)
        self.last_attempt: Optional[dict] = None
        # Thread safety
        self._lock = threading.Lock()

    def set_last_attempt(self, roll_number: str, status: str, details: dict):
        """Record the result of the last processing attempt for debugging."""
        with self._lock:
            self.last_attempt = {
                "roll_number": roll_number,
                "status": status,
                "timestamp": datetime.now(LOCAL_TZ).isoformat(),
                "details": details
            }

    def get_last_attempt(self) -> Optional[dict]:
        with self._lock:
            return self.last_attempt

    def get_total_records(self) -> int:
        with self._lock:
            return len(self.history)

    def mark_attendance_atomic(
        self, 
        roll_number: str, 
        session_id: str, 
        instructor_id: str, 
        confidence: float, 
        enable_daily_limit: bool = False
    ) -> Tuple[Optional[dict], Optional[str]]:
        """
        Atomically checks for session duplicates and optional daily limits.
        Returns: (record, error_code)
        """
        roll_no = roll_number.strip().upper()
        today = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
        
        with self._lock:
            # 1. Session Duplicate Check
            if session_id in self.records and roll_no in self.records[session_id]:
                return None, "DUPLICATE_ATTENDANCE"

            # 2. Optional Daily Limit Check
            if enable_daily_limit:
                if today not in self.daily_registry:
                    self.daily_registry[today] = {}
                if roll_no in self.daily_registry[today]:
                    return None, "DAILY_LIMIT_REACHED"

            # 3. Prepare the verified attendance record
            record_id = str(uuid.uuid4())
            record = {
                "attendance_id": record_id,
                "roll_number": roll_no,
                "session_id": session_id,
                "instructor_id": instructor_id,
                "timestamp": datetime.now(LOCAL_TZ).isoformat(),
                "identity_verified": True,
                "confidence": confidence,
                "status": "marked"
            }

            # 4. Final Atomic Save
            if session_id not in self.records:
                self.records[session_id] = {}
            
            self.records[session_id][roll_no] = record
            
            if enable_daily_limit:
                self.daily_registry[today][roll_no] = True
            
            self.history.append(record)
            return record, None

    def get_by_session(self, session_id: str) -> List[dict]:
        with self._lock:
            session_data = self.records.get(session_id, {})
            return list(session_data.values())

    def get_by_student(self, roll_number: str) -> List[dict]:
        with self._lock:
            return [r for r in self.history if r["roll_number"] == roll_number.upper()]

db = AttendanceStore()
