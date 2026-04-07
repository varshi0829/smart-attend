import os

# Internal Service URLs
FACE_SERVICE_URL = os.getenv("FACE_SERVICE_URL", "https://127.0.0.1:5001")
QR_SERVICE_URL = os.getenv("QR_SERVICE_URL", "https://127.0.0.1:5002")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")

# Request Settings
SERVICE_TIMEOUT = 10.0 # Seconds
INTERNAL_TLS_VERIFY = os.getenv("INTERNAL_TLS_VERIFY", "false").lower() == "true"

# Attendance Rules
ENABLE_DAILY_LIMIT = os.getenv("ENABLE_DAILY_LIMIT", "False").lower() == "true"
ATTENDANCE_TIMEZONE = os.getenv("ATTENDANCE_TIMEZONE", "Asia/Kolkata")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Reports Storage
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
