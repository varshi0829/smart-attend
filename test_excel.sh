#!/bin/bash
# Excel Generation End-to-End Test

set -e

echo "=========================================="
echo "Excel Generation Test"
echo "=========================================="
echo ""

# Config
INSTRUCTOR_ID="INST_001"
CLASS_NAME="CSE-A"
QR_API="https://127.0.0.1:5002"
ATTENDANCE_API="https://127.0.0.1:5003"

echo "✓ Starting session..."
START_RESP=$(curl -sk -X POST "$QR_API/session/start" \
  -H "Content-Type: application/json" \
  -d "{\"instructor_id\":\"$INSTRUCTOR_ID\",\"class_name\":\"$CLASS_NAME\"}")

SESSION_ID=$(echo "$START_RESP" | grep -o '"session_id":"[^"]*' | cut -d'"' -f4)

if [ -z "$SESSION_ID" ]; then
  echo "✗ Failed to start session"
  echo "Response: $START_RESP"
  exit 1
fi

echo "  Session ID: $SESSION_ID"
echo ""

echo "✓ Waiting 2 seconds..."
sleep 2
echo ""

echo "✓ Stopping session (triggers Excel)..."
STOP_RESP=$(curl -sk -X POST "$QR_API/session/stop" \
  -H "Content-Type: application/json" \
  -d "{\"instructor_id\":\"$INSTRUCTOR_ID\"}")

echo "  Response: $STOP_RESP"
echo ""

echo "✓ Waiting 3 seconds for Excel generation..."
sleep 3
echo ""

echo "✓ Checking reports folder..."
SESSION_PREFIX="${SESSION_ID:0:8}"
REPORTS_DIR="./attendance-service/reports"

if ls "$REPORTS_DIR"/*"$SESSION_PREFIX"*.xlsx 1> /dev/null 2>&1; then
  echo "  ✓ Excel file found:"
  ls -lh "$REPORTS_DIR"/*"$SESSION_PREFIX"*.xlsx | awk '{print "    " $9 " (" $5 ")"}'
else
  echo "  ✗ Excel file NOT found"
  echo "  Files in reports:"
  ls -lh "$REPORTS_DIR"/ 2>/dev/null | tail -n +2 | awk '{print "    " $9}' || echo "    (empty)"
  echo ""
  echo "  Checking logs..."
  echo "  QR Service:"
  tail -5 logs/qr-service.log | sed 's/^/    /'
  echo "  Attendance Service:"
  tail -5 logs/attendance-service.log | sed 's/^/    /'
  exit 1
fi
echo ""

echo "✓ Testing download endpoint..."
DOWNLOAD_RESP=$(curl -sk -w "\n%{http_code}" "$ATTENDANCE_API/attendance/session/$SESSION_ID/download-report" -o test_download.xlsx)
HTTP_CODE=$(echo "$DOWNLOAD_RESP" | tail -1)

if [ "$HTTP_CODE" = "200" ] && [ -f "test_download.xlsx" ]; then
  SIZE=$(stat -c%s "test_download.xlsx" 2>/dev/null || stat -f%z "test_download.xlsx" 2>/dev/null)
  if [ "$SIZE" -gt 1000 ]; then
    echo "  ✓ Download successful (${SIZE} bytes)"
    rm test_download.xlsx
  else
    echo "  ✗ File too small (${SIZE} bytes)"
    exit 1
  fi
else
  echo "  ✗ Download failed (HTTP $HTTP_CODE)"
  exit 1
fi
echo ""

echo "=========================================="
echo "✓ ALL TESTS PASSED"
echo "=========================================="
echo ""
echo "Excel generation is working correctly!"
echo ""
