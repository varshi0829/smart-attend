# Smart Attendance System (SmartAttend)
### AI-Powered Face Recognition + Dynamic QR Verification

**Status:** Phase 1B Complete ✅ | **Current Phase:** Phase 2 (Face Recognition Service) 🚀

---

## 📋 Overview
SmartAttend is a secure attendance management system designed to eliminate proxy attendance. It uses a dual-verification process:
1. **Face Recognition:** Identifies the student using AI.
2. **Dynamic QR Code:** Ensures physical presence via a time-sensitive, rotating QR code (45-second refresh).

---

## ✨ Key Features (Phase 1B)
- **Dynamic QR System:** Tamper-proof JWT-signed tokens that refresh every 45 seconds.
- **Secure Authentication:** Role-based access control (RBAC) for Instructors and Students using JWT.
- **Session Management:** Instructors can start/stop sessions and monitor live attendance.
- **8-Step Validation:** Rigorous backend checks (Face, QR signature, Expiry, Currency, Duplicates, etc.).
- **Mobile-Ready:** Optimized for scanning and selfie capture on mobile devices.

---

## 🛠️ Tech Stack
- **Backend:** Node.js, Express.js, MongoDB (Mongoose)
- **Face Service:** Python (Flask), MTCNN, FaceNet (Upcoming in Phase 2)
- **Frontend:** HTML5, TailwindCSS, Vanilla JS (Planned React/Vue migration)
- **Real-time:** WebSockets (Socket.io) for live attendance updates.

---

## 📂 Project Structure
```text
smart-attend/
├── backend/                # Node.js API Server
├── face-service/           # Python AI Service (Phase 2)
├── frontend-instructor/    # Instructor Dashboard
├── frontend-student/       # Student Portal
├── docs/                   # Detailed System Documentation (11 files)
├── IMPLEMENTATION_GUIDE.md # MASTER GUIDE (Consolidated Plan & Testing)
└── README.md               # This file
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Node.js (v18+)
- MongoDB (Local or Atlas)
- Python (v3.9+)

### 2. Setup Backend
```bash
cd backend
npm install
npm start
```

### 3. Setup Frontend
The frontend files are currently static and can be served using any local server (e.g., Live Server in VS Code) on ports 8000 (Student) and 8001 (Instructor).

### 4. Running Tests
Refer to the **Testing Guide** section in `IMPLEMENTATION_GUIDE.md` for complete `curl` commands and automated test scripts.

---

## 🗺️ Roadmap
- [x] **Phase 1A:** Database Schema & Auth Foundation
- [x] **Phase 1B:** Dynamic QR System & Session Management
- [ ] **Phase 2:** Python Face Recognition Service (Integration)
- [ ] **Phase 3:** Real-time WebSocket Integration
- [ ] **Phase 4:** Advanced Analytics & Reporting
- [ ] **Phase 5:** Mobile App (React Native/Flutter)

---

## 📚 Documentation
For detailed architectural designs, API specs, and security protocols, explore the `/docs` directory or read the consolidated **[IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md)**.

---

## 🛡️ Security
SmartAttend implements multiple layers of security:
- **Screenshot Protection:** QR tokens expire in 45 seconds.
- **Replay Protection:** Unique nonces per token.
- **Identity Lock:** Attendance is only marked if the face matches the account owner.
- **Atomic Ops:** Database transactions ensure data integrity.

---

**Last Updated:** March 7, 2026  
**Developer:** Senior AI Engineer (Gemini CLI)
