import os

# Internal Service URLs
FACE_SERVICE_URL = os.getenv("FACE_SERVICE_URL", "https://127.0.0.1:5001")

# QR Settings
QR_EXPIRY_SECONDS = 15 # Reduced from 45 for higher security
SERVICE_TIMEOUT = 10.0
INTERNAL_TLS_VERIFY = os.getenv("INTERNAL_TLS_VERIFY", "false").lower() == "true"
