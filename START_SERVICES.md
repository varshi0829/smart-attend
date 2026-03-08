# Start Services - Commands

## Terminal 1: Flask Face Service (Port 5001)

```bash
cd face-service
pip install -r requirements.txt
python app.py
```

Expected output:
```
* Running on http://0.0.0.0:5001
```

---

## Terminal 2: Node Backend (Port 5000)

```bash
cd backend
npm install
npm start
```

Expected output:
```
Server running on port 5000
MongoDB connected
```

---

## Verify Services

```bash
# Check Flask service
curl http://localhost:5001/health

# Check Node backend
curl http://localhost:5000/api/health
```

---

## Configuration

**backend/.env:**
```
FACE_SERVICE_URL=http://localhost:5001
```

**backend/package.json:**
- axios dependency added

**face-service/app.py:**
- Port changed to 5001

---

## Face Verification Flow

1. Student sends: `POST /api/student/attendance/mark`
   ```json
   {
     "qrToken": "...",
     "faceImage": "data:image/jpeg;base64,..."
   }
   ```

2. Backend calls: `POST http://localhost:5001/face/verify`
   ```json
   {
     "studentId": "65f...",
     "faceImage": "data:image/jpeg;base64,..."
   }
   ```

3. Flask returns:
   ```json
   {
     "verified": true,
     "confidence": 0.87
   }
   ```

4. If service unavailable → HTTP 503
   ```json
   {
     "error": "Face verification service unavailable"
   }
   ```

5. If verified = false → HTTP 400
   ```json
   {
     "error": "Face verification failed",
     "confidence": 0.42
   }
   ```

6. If verified = true → Continue Phase 1B QR validation

---

## All Phase 1B Rules Preserved ✓

- QR expires in 45 seconds
- Session must be active
- QR must match current token
- Duplicate attendance fails
