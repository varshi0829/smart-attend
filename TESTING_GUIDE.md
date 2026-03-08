# 🧪 SmartAttend Testing Guide (Phase 1B)
This guide provides a step-by-step process for running and verifying the SmartAttend system, including the Face and QR services.

---

## 🏗️ Step 1: Start All Services

Open **three** separate terminal windows and run the following:

### Terminal 1: Face Service (AI/ML)
```bash
cd face-service
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```
**Expected:** `* Running on http://0.0.0.0:5001`

### Terminal 2: Backend API (Node.js)
```bash
cd backend
npm install
npm run dev
```
**Expected:** `MongoDB connected` and `Server running on port 5000`

### Terminal 3: Quick Health Check
Run these commands to verify connection:
```bash
# Check Face Service
curl http://localhost:5001/health

# Check Backend API
curl http://localhost:5000/api/health
```

---

## 🛠️ Step 2: Manual Testing (Using Curl)

### 1. Instructor: Login & Start Session
First, login to get your `INSTRUCTOR_TOKEN`:
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"instructor@example.com","password":"password123"}'
```
**Now start a session:**
```bash
curl -X POST http://localhost:5000/api/instructor/session/start \
  -H "Authorization: Bearer INSTRUCTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"className":"CSE-A","subject":"Data Structures"}'
```
**Important:** Copy the `id` (Session ID) and `qrToken` from the response.

### 2. Student: Login & Mark Attendance
First, login as a student to get your `STUDENT_TOKEN`:
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"student@example.com","password":"password123"}'
```
**Mark attendance:**
```bash
curl -X POST http://localhost:5000/api/student/attendance/mark \
  -H "Authorization: Bearer STUDENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"qrToken":"PASTE_QR_TOKEN_HERE","faceVerified":true}'
```

---

## 🤖 Step 3: Automated Test Script
For quick verification, you can run the automated test script:

1. **Make it executable:**
   ```bash
   chmod +x quick_test.sh
   ```
2. **Run the script:**
   ```bash
   ./quick_test.sh instructor@example.com student@example.com password123
   ```

---

## 🧪 Test Scenarios & Expected Results

| Scenario | Action | Expected Result |
| :--- | :--- | :--- |
| **Success Case** | Valid Face + Valid QR | `{"success":true,"message":"Attendance marked"}` |
| **Expired QR** | Use QR after 45 seconds | `{"error":"QR token expired"}` |
| **Duplicate** | Mark attendance twice | `{"error":"Attendance already marked"}` |
| **No Face** | Send `faceVerified: false` | `{"error":"Face verification failed"}` |
| **Wrong QR** | Use random string | `{"error":"Invalid QR token"}` |
| **Stopped Session** | Mark after stopping | `{"error":"Session is not active"}` |

---

## 📊 Live Monitoring
To see the attendance feed as an instructor:
```bash
curl -X GET http://localhost:5000/api/instructor/session/SESSION_ID \
  -H "Authorization: Bearer INSTRUCTOR_TOKEN"
```

---

## 🛑 Troubleshooting
1. **MongoDB Connection Failed:** Check if `mongod` is running or if your `.env` connection string is correct.
2. **Face Service Port Error:** Ensure no other service is using port 5001 (`lsof -i :5001`).
3. **QR Token Mismatch:** Remember tokens refresh every 45 seconds. Use the **latest** token from the instructor dashboard.

---

**Next Action:** You can now proceed to **Phase 2 (Frontend Integration)**.
