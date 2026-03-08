import os

# Internal Service URLs
FACE_SERVICE_URL = os.getenv("FACE_SERVICE_URL", "http://localhost:5001")
QR_SERVICE_URL = os.getenv("QR_SERVICE_URL", "http://localhost:5002")

# Request Settings
SERVICE_TIMEOUT = 10.0 # Seconds

# Attendance Rules
ENABLE_DAILY_LIMIT = os.getenv("ENABLE_DAILY_LIMIT", "False").lower() == "true"
ATTENDANCE_TIMEZONE = os.getenv("ATTENDANCE_TIMEZONE", "Asia/Kolkata")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
