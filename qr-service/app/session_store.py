import uuid
import secrets
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

    def start_session(self, instructor_id: str, class_name: str):
        if instructor_id in self.instructor_to_session:
            # Cleanup old session if it exists but wasn't stopped properly
            old_sid = self.instructor_to_session[instructor_id]
            self.sessions_db.pop(old_sid, None)

        session_id = str(uuid.uuid4())
        session_data = {
            "id": session_id,
            "instructor_id": instructor_id,
            "class_name": class_name,
            "status": "active",
            "created_at": datetime.now(timezone.utc),
        }
        
        self.instructor_to_session[instructor_id] = session_id
        self.sessions_db[session_id] = session_data
        return session_data, None

    def generate_fresh_code(self, instructor_id: str, ttl: int) -> Tuple[Optional[str], Optional[datetime]]:
        session_id = self.instructor_to_session.get(instructor_id)
        if not session_id:
            return None, None
        
        # MANDATORY FIX: Invalidate ALL previous tokens for this specific session.
        old_codes = [c for c, data in self.active_codes.items() if data["session_id"] == session_id]
        removed_count = len(old_codes)
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
        
        self._cleanup_expired_codes()
        return new_code, expiry

    def _cleanup_expired_codes(self):
        now = datetime.now(timezone.utc)
        expired = [c for c, data in self.active_codes.items() if now > data["expires_at"]]
        for c in expired:
            self.active_codes.pop(c, None)

    def get_active_session(self, instructor_id: str):
        session_id = self.instructor_to_session.get(instructor_id)
        return self.sessions_db.get(session_id) if session_id else None

    def stop_session(self, instructor_id: str):
        session_id = self.instructor_to_session.pop(instructor_id, None)
        if not session_id:
            return None, "No active session found."
        
        session = self.sessions_db.get(session_id)
        if session:
            session["status"] = "stopped"
            session["ended_at"] = datetime.now(timezone.utc)
            
            # Invalidate all codes for this session
            codes_to_remove = [c for c, data in self.active_codes.items() if data["session_id"] == session_id]
            for c in codes_to_remove:
                self.active_codes.pop(c, None)
                
        return session, None

    def verify_code(self, code: str) -> Tuple[Optional[dict], Optional[str]]:
        """Verify the short code and return the session data."""
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

store = SessionStore()
