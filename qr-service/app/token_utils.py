from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from .config import SECRET_KEY, ALGORITHM, QR_EXPIRY_SECONDS

def create_qr_token(session_id: str, instructor_id: str):
    """Generate a signed JWT for the QR code with session and instructor IDs."""
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=QR_EXPIRY_SECONDS)
    
    payload = {
        "sid": session_id,
        "iid": instructor_id,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp())
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM), now, expires

def decode_qr_token(token: str):
    """Verify signature and return payload or error status."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload, "OK"
    except jwt.ExpiredSignatureError:
        return None, "EXPIRED"
    except JWTError:
        return None, "INVALID"
