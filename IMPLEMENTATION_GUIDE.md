# Smart Attendance System - Master Implementation Guide
# Face Recognition + Dynamic QR Verification

---

## 📋 System Overview

**Goal:** Build a robust attendance system that prevents proxy attendance using two-factor verification:
1. **Face Recognition:** Verifies the student's identity using AI.
2. **Dynamic QR Code:** Verifies the student is physically present in the classroom (refreshes every 45s).

---

## 🏗️ System Architecture

```
┌─────────────────┐         ┌─────────────────┐
│ Instructor App  │         │  Student App    │
│   (HTML/JS)     │         │   (HTML/JS)     │
│   Port: 8001    │         │   Port: 8000    │
└────────┬────────┘         └────────┬────────┘
         │                           │
         └───────────┬───────────────┘
                     │ HTTPS
         ┌───────────▼────────────┐
         │   Backend API Server   │
         │   (Node.js/Express)    │
         │   Port: 5000           │
         └───────┬────────┬───────┘
                 │        │
        ┌────────▼──┐  ┌──▼──────────┐
        │ MongoDB   │  │ Face Service│
        │ Database  │  │  (Python)   │
        │           │  │  Port: 5001 │
        └───────────┘  └─────────────┘
```

---

## 📦 Phase 1: Backend Foundation (Complete ✅)

### Core Components:
- **Database Models:** User, Session, Attendance, FaceData.
- **Auth System:** JWT-based login/register with role-based access.
- **Session Management:** Instructor starts/stops attendance sessions.
- **Dynamic QR System:** 
  - JWT-signed QR tokens refreshed every 45 seconds.
  - Nonce-based replay attack prevention.
  - Screenshot prevention via token currency validation.

### API Flow:
**Instructor:**
1. `POST /api/auth/login` → Get token
2. `POST /api/instructor/session/start` → Create session + QR
3. `GET /api/instructor/session/:id/qr` → Refresh QR (every 45s)
4. `GET /api/instructor/session/:id` → Monitor attendance
5. `POST /api/instructor/session/:id/stop` → End session

**Student:**
1. `POST /api/auth/login` → Get token
2. `POST /api/student/attendance/mark` → Submit face + QR
3. `GET /api/student/attendance/history` → View records

---

## 🤖 Phase 2: Face Recognition Service (Next Step 🚀)

### Implementation Plan:
1. **Python Flask Service:** Dedicated service for CPU-heavy face tasks.
2. **Face Detection:** Using MTCNN or Dlib.
3. **Embedding Extraction:** Using FaceNet or ArcFace.
4. **Similarity Comparison:** Cosine similarity with thresholding.
5. **Endpoints:**
   - `POST /register-face`: Upload images to create student embeddings.
   - `POST /verify-face`: Compare live capture against stored embeddings.

### Directory Structure:
```
face-service/
├── app/
│   ├── main.py
│   ├── face_logic.py
│   └── utils.py
├── embeddings/
│   └── (stored .pkl files)
├── requirements.txt
└── run.py
```

---

## 🧪 Testing Guide

### Prerequisites
1. Start Backend: `cd backend && npm start`
2. Start MongoDB: Ensure your local or Atlas instance is running.

### Manual Test Commands (Curl)

#### 1. Login
```bash
# Instructor Login
curl -X POST http://localhost:5000/api/auth/login -H "Content-Type: application/json" -d '{"email":"instructor@example.com","password":"password123"}'

# Student Login
curl -X POST http://localhost:5000/api/auth/login -H "Content-Type: application/json" -d '{"email":"student@example.com","password":"password123"}'
```

#### 2. Session Management
```bash
# Start Session
curl -X POST http://localhost:5000/api/instructor/session/start -H "Authorization: Bearer INSTRUCTOR_TOKEN" -H "Content-Type: application/json" -d '{"className":"CSE-A","subject":"Data Structures"}'

# Get current QR
curl -X GET http://localhost:5000/api/instructor/session/SESSION_ID/qr -H "Authorization: Bearer INSTRUCTOR_TOKEN"
```

#### 3. Marking Attendance
```bash
curl -X POST http://localhost:5000/api/student/attendance/mark -H "Authorization: Bearer STUDENT_TOKEN" -H "Content-Type: application/json" -d '{"qrToken":"TOKEN_HERE","faceVerified":true}'
```

### Automated Quick Test Script
Save as `quick_test.sh`:
```bash
#!/bin/bash
# A simple script to test the Phase 1B flow
# Usage: ./quick_test.sh [instructor_email] [student_email] [password]
# ... (Script logic here)
```

---

## 📊 8-Step Validation Process (Student Side)

1. **Face verification status check** (faceVerified = true)
2. **JWT signature verification** (verifyQRToken)
3. **Token expiration check** (45 seconds)
4. **Session existence check** (findById)
5. **Session status check** (status = 'active')
6. **QR token currency check** (matches currentQRToken)
7. **QR expiry from session** (qrExpiresAt)
8. **Duplicate attendance check** (unique index)

---

## 🛡️ Security Design
- **Tamper-proof tokens:** QR tokens are signed JWTs.
- **Physical presence:** 45s refresh prevents remote scanning from photos/screenshots.
- **Identity Lock:** Face recognition ensures the account owner is the one scanning.
- **Replay Protection:** Nonces ensure a token can't be reused if captured.
- **Role Isolation:** Instructors cannot mark themselves present; students cannot start sessions.

---

## 🚀 Deployment Strategy
- **Backend:** Node.js on Render/AWS/DigitalOcean.
- **Database:** MongoDB Atlas.
- **Face Service:** Python on AWS EC2 or specialized AI hosting.
- **Frontend:** Static hosting (Vercel/Netlify/GitHub Pages).

---

## 📊 Implementation Checklist

### Phase 1: Backend Foundation (DONE)
- [x] Auth system
- [x] Session management
- [x] Dynamic QR generator
- [x] Attendance marking API
- [x] Role-based security

### Phase 2: Face Recognition (PENDING)
- [ ] Flask service setup
- [ ] Embedding extraction logic
- [ ] Face comparison API
- [ ] Integration with Node.js backend

### Phase 3: Frontend (PENDING)
- [ ] Student dashboard (QR Scanner + Camera)
- [ ] Instructor dashboard (QR Display + Live feed)
- [ ] Real-time updates via WebSockets

---

**Next Action:** Move to Phase 2 - Build the Python Face Recognition Service.
