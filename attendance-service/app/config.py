import os
import logging

# Setup logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger("AttendanceService")

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

# Reports Storage
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
INSTRUCTOR_CONFIG_PATH = os.path.join(BASE_DIR, "instructor_config.json")

# ── Mail / SMTP config ────────────────────────────────────────────────────────
# Set these via environment variables. Never hardcode credentials.
# See attendance-service/.env for the template.
MAIL_ENABLED   = os.getenv("MAIL_ENABLED", "false").lower() == "true"
SMTP_HOST      = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT      = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME  = os.getenv("SMTP_USERNAME", "smartattenBVRITH@gmail.com")
SMTP_PASSWORD  = os.getenv("SMTP_PASSWORD", "").replace(" ", "")  # Gmail App Passwords shown with spaces; strip them
MAIL_FROM      = os.getenv("MAIL_FROM", "smartattenBVRITH@gmail.com")
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "SmartAttend")
