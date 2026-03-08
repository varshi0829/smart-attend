import os

# Security
SECRET_KEY = os.getenv("QR_SECRET_KEY", "prod-secret-qr-key-2026-v1")
ALGORITHM = "HS256"

# Token Expiry (Seconds)
# Reverted to 45s to match the rotation interval.
# The session_store now enforces that only the latest token is valid.
QR_EXPIRY_SECONDS = 45

# Database (Placeholder for future)
DATABASE_URL = "sqlite:///./sessions.db"
