import uuid
import secrets
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple, Set

class SessionStore:
    def __init__(self):
        # {instructor_id: session_id}
        self.instructor_to_session: Dict[str, str] = {}
        # {session_id: session_data}
        self.sessions_db: Dict[str, dict] = {}
        # {short_code: {"session_id": str, "expires_at": datetime}}
        self.active_codes: Dict[str, dict] = {}
        # {grant_id: grant_data}
        self.scan_grants: Dict[str, dict] = {}
        # Thread safety
        self._lock = threading.Lock()

    def start_session(self, instructor_id: str, class_name: str):
        with self._lock:
            if instructor_id in self.instructor_to_session:
                # Cleanup old session if it exists but wasn't stopped properly
                old_sid = self.instructor_to_session[instructor_id]
                self.sessions_db.pop(old_sid, None)

            session_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            session_data = {
                "id": session_id,
                "instructor_id": instructor_id,
                "class_name": class_name,
                "status": "active",
                "created_at": now,
                "start_time": now,  # For Excel report
            }
            
            self.instructor_to_session[instructor_id] = session_id
            self.sessions_db[session_id] = session_data
            return session_data, None

    def create_grant(self, roll_number: str, session_id: str, instructor_id: str) -> dict:
        """Create a short-lived (30s) scan grant for a specific student and session."""
        roll_no = roll_number.upper().strip()
        
        with self._lock:
            # Invalidate any existing unused grants for this roll + session
            to_invalidate = [
                gid for gid, g in self.scan_grants.items()
                if g["roll_number"] == roll_no and g["session_id"] == session_id and not g["used"]
            ]
            for gid in to_invalidate:
                self.scan_grants.pop(gid, None)

            grant_id = "GRANT_" + secrets.token_urlsafe(16)
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=30)

            grant_data = {
                "grant_id": grant_id,
                "roll_number": roll_no,
                "session_id": session_id,
                "instructor_id": instructor_id,
                "issued_at": now,
                "expires_at": expires_at,
                "used": False,
                "retries": 0
            }
            self.scan_grants[grant_id] = grant_data
            self._cleanup_expired_grants_unlocked()
            return grant_data

    def verify_grant(self, grant_id: str, roll_number: str, session_id: str) -> Tuple[Optional[dict], Optional[str]]:
        """Verify the grant exists, matches roll/session, is unused and not expired."""
        self._cleanup_expired_grants()
        with self._lock:
            grant = self.scan_grants.get(grant_id)
            if not grant:
                return None, "INVALID_SCAN_GRANT"
            
            if grant["roll_number"] != roll_number.upper().strip():
                return None, "GRANT_ROLL_MISMATCH"
                
            if grant["session_id"] != session_id:
                return None, "GRANT_SESSION_MISMATCH"

            if grant["used"]:
                return None, "USED_SCAN_GRANT"

            if datetime.now(timezone.utc) > grant["expires_at"]:
                return None, "SCAN_GRANT_EXPIRED"

            # Also check if the underlying session is still active
            session = self.sessions_db.get(session_id)
            if not session or session["status"] != "active":
                return None, "SESSION_CLOSED"

            return grant, None

    def increment_grant_retry(self, grant_id: str) -> int:
        """Increment retry count and invalidate if limit (3) reached."""
        with self._lock:
            grant = self.scan_grants.get(grant_id)
            if not grant: return 0
            
            grant["retries"] = grant.get("retries", 0) + 1
            if grant["retries"] >= 3:
                grant["used"] = True # Invalidate grant after 3 failed face matches
            
            return grant["retries"]

    def consume_grant(self, grant_id: str) -> bool:
        """Atomically mark the grant as used."""
        with self._lock:
            grant = self.scan_grants.get(grant_id)
            if grant and not grant["used"]:
                # Check expiry again just in case
                if datetime.now(timezone.utc) > grant["expires_at"]:
                    return False
                grant["used"] = True
                return True
            return False

    def generate_fresh_code(self, instructor_id: str, ttl: int) -> Tuple[Optional[str], Optional[datetime]]:
        with self._lock:
            session_id = self.instructor_to_session.get(instructor_id)
            if not session_id:
                return None, None
            
            # MANDATORY FIX: Invalidate ALL previous tokens for this specific session.
            old_codes = [c for c, data in self.active_codes.items() if data["session_id"] == session_id]
            for c in old_codes:
                self.active_codes.pop(c, None)
            
            # Generate short secure random code with SmartAttend prefix
            new_code = "SA_" + secrets.token_urlsafe(12) 
            expiry = datetime.now(timezone.utc) + timedelta(seconds=ttl)
            
            # Map this code to the session
            self.active_codes[new_code] = {
                "session_id": session_id,
                "expires_at": expiry
            }
            
            self._cleanup_expired_codes_unlocked()
            return new_code, expiry

    def _cleanup_expired_codes_unlocked(self):
        now = datetime.now(timezone.utc)
        expired = [c for c, data in self.active_codes.items() if now > data["expires_at"]]
        for c in expired:
            self.active_codes.pop(c, None)

    def _cleanup_expired_grants(self):
        with self._lock:
            self._cleanup_expired_grants_unlocked()

    def _cleanup_expired_grants_unlocked(self):
        now = datetime.now(timezone.utc)
        expired = [gid for gid, g in self.scan_grants.items() if now > g["expires_at"]]
        for gid in expired:
            self.scan_grants.pop(gid, None)

    def get_active_session(self, instructor_id: str):
        with self._lock:
            session_id = self.instructor_to_session.get(instructor_id)
            return self.sessions_db.get(session_id) if session_id else None

    def stop_session(self, instructor_id: str):
        with self._lock:
            session_id = self.instructor_to_session.pop(instructor_id, None)
            if not session_id:
                return None, "No active session found."
            
            session = self.sessions_db.get(session_id)
            if session:
                now = datetime.now(timezone.utc)
                session["status"] = "stopped"
                session["ended_at"] = now
                session["end_time"] = now  # For Excel report
                
                # Invalidate all codes for this session
                codes_to_remove = [c for c, data in self.active_codes.items() if data["session_id"] == session_id]
                for c in codes_to_remove:
                    self.active_codes.pop(c, None)

                # ALSO invalidate all grants for this session
                grants_to_remove = [gid for gid, g in self.scan_grants.items() if g["session_id"] == session_id]
                for gid in grants_to_remove:
                    self.scan_grants.pop(gid, None)
                    
            return session, None

    def verify_code(self, code: str) -> Tuple[Optional[dict], Optional[str]]:
        """Verify the short code and return the session data."""
        with self._lock:
            code_data = self.active_codes.get(code)
            
            if not code_data:
                return None, "INVALID_CODE"
                
            if datetime.now(timezone.utc) > code_data["expires_at"]:
                self.active_codes.pop(code, None)
                return None, "CODE_EXPIRED"
                
            session_id = code_data["session_id"]
            session = self.sessions_db.get(session_id)
            
            if not session or session["status"] != "active":
                return None, "SESSION_CLOSED"
                
            return session, None

    def get_session_by_id(self, session_id: str) -> Optional[dict]:
        """Get session data by session ID (for Excel generation)."""
        with self._lock:
            return self.sessions_db.get(session_id)

store = SessionStore()
