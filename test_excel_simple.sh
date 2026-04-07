#!/bin/bash
# Simple Excel Generation Test

echo "=========================================="
echo "Excel Generation Test"
echo "=========================================="
echo ""

INSTRUCTOR_ID="INST_001"
CLASS_NAME="CSE-A"
QR_API="https://127.0.0.1:5002"
ATTENDANCE_API="https://127.0.0.1:5003"

echo "1. Starting session..."
START_RESP=$(curl -sk -X POST "$QR_API/session/start" \
  -H "Content-Type: application/json" \
  -d "{\"instructor_id\":\"$INSTRUCTOR_ID\",\"class_name\":\"$CLASS_NAME\"}")

SESSION_ID=$(echo "$START_RESP" | grep -o '"session_id":"[^"]*' | cut -d'"' -f4)
echo "   Session: $SESSION_ID"
echo ""

echo "2. Manually triggering Excel generation..."
GEN_RESP=$(curl -sk -X POST "$ATTENDANCE_API/attendance/session/$SESSION_ID/generate-report")
echo "   Response: $GEN_RESP"
echo ""

echo "3. Checking if file was created..."
SESSION_PREFIX="${SESSION_ID:0:8}"
REPORTS_DIR="./attendance-service/reports"

sleep 2

if ls "$REPORTS_DIR"/*"$SESSION_PREFIX"*.xlsx 1> /dev/null 2>&1; then
  echo "   ✓ Excel file created:"
  ls -lh "$REPORTS_DIR"/*"$SESSION_PREFIX"*.xlsx
  echo ""
  echo "   ✓ SUCCESS: Excel generation works!"
else
  echo "   ✗ No Excel file found"
  echo ""
  echo "   Logs:"
  tail -15 logs/attendance-service.log | grep -E "EXCEL|ERROR"
fi
echo ""

echo "4. Stopping session..."
curl -sk -X POST "$QR_API/session/stop" \
  -H "Content-Type: application/json" \
  -d "{\"instructor_id\":\"$INSTRUCTOR_ID\"}" > /dev/null
echo "   ✓ Session stopped"
echo ""
