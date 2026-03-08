# System Overview
# QR + Face Recognition Based Attendance Management System

**Version:** 1.0  
**Date:** March 7, 2026  
**Document Type:** Technical Design Specification

---

## 1.1 Project Objective

The QR + Face Recognition Based Attendance Management System is designed to automate and secure the attendance marking process in educational institutions. The system eliminates traditional manual attendance methods and prevents proxy attendance through dual verification: biometric face recognition and location-based QR code scanning.

---

## 1.2 Core Problem Statement

Traditional attendance systems suffer from:
- **Proxy attendance**: Students marking attendance for absent peers
- **Time-consuming manual roll calls**: 10-15 minutes per class wasted
- **Paper-based record keeping**: Prone to errors and loss
- **Lack of real-time tracking**: No immediate visibility of attendance
- **Difficulty in generating reports**: Manual compilation required
- **No verification mechanism**: Cannot confirm physical presence

---

## 1.3 Solution Approach

This system implements a **dual-factor verification mechanism**:

### Factor 1: Biometric Verification (WHO)
- Face recognition ensures the correct student is present
- Uses dataset-based embedding comparison (Kaggle-style)
- Prevents impersonation and proxy attendance

### Factor 2: Location Verification (WHERE)
- QR code scanning ensures physical presence in classroom
- Dynamic QR codes refresh every 45 seconds
- Prevents remote attendance marking

### Critical Rule
**Attendance is marked ONLY when BOTH conditions are satisfied simultaneously.**

If face verification passes but QR scan fails → No attendance  
If QR scan passes but face verification fails → No attendance  
Both must succeed → Attendance marked ✓

---

## 1.4 System Benefits

### For Instructors
- **Instant session creation**: Start attendance in < 5 seconds
- **Real-time monitoring**: See who marked attendance live
- **Automated record keeping**: No manual entry required
- **Elimination of roll calls**: Save 10-15 minutes per class
- **Prevention of proxy attendance**: 100% identity verification
- **Detailed analytics**: Attendance patterns and trends
- **Easy report generation**: Export to CSV/PDF

### For Students
- **Quick attendance marking**: Complete in < 30 seconds
- **Transparent records**: View attendance history anytime
- **Instant confirmation**: Know immediately if attendance marked
- **No waiting in queues**: Mark attendance from seat
- **Historical tracking**: Monitor own attendance percentage

### For Institution
- **Accurate attendance data**: Eliminate human errors
- **Reduced administrative overhead**: Automated processes
- **Enhanced security**: Biometric + location verification
- **Data-driven insights**: Identify attendance patterns
- **Compliance**: Maintain accurate records for audits
- **Cost savings**: Reduce paper and manual labor

---

## 1.5 Key Features

### Session Management
- One-click session start/stop
- Automatic QR code generation
- Real-time session status tracking
- Session history and analytics

### Dynamic QR System
- Auto-refresh every 45 seconds
- Cryptographically signed tokens
- Prevents screenshot attacks
- Immediate invalidation on session stop

### Face Recognition
- Dataset-based approach (Kaggle-style)
- Pre-trained embedding models
- Similarity-based matching
- Configurable threshold

### Security
- JWT authentication
- Signed QR tokens
- Backend validation
- Replay attack prevention
- Duplicate attendance prevention

### Real-Time Updates
- Live attendance notifications
- WebSocket-based communication
- Instant dashboard updates
- Session status broadcasting

---

## 1.6 System Scope

### In Scope
- Instructor web application
- Student web application
- Backend API server
- Face recognition service
- QR code generation and validation
- Real-time updates
- Attendance record management
- User authentication
- Session management
- Attendance history and reports

### Out of Scope
- Mobile native applications (future enhancement)
- Biometric hardware integration
- Payment/fee management
- Grade management
- Course content management
- Student information system integration
- Email/SMS notifications (future enhancement)
- Advanced analytics dashboard (future enhancement)

---

## 1.7 User Roles

### Instructor
**Responsibilities:**
- Create and manage attendance sessions
- Start/stop sessions
- Monitor live attendance
- View attendance reports
- Manage class information

**Access:**
- Instructor web app
- Session management APIs
- Attendance reports
- Student attendance records

### Student
**Responsibilities:**
- Register face data
- Mark attendance (face + QR)
- View personal attendance history
- Update profile information

**Access:**
- Student web app
- Face registration/verification APIs
- Personal attendance records
- QR scanning functionality

---

## 1.8 System Constraints

### Technical Constraints
- Requires camera access for face capture and QR scanning
- Requires internet connectivity
- Browser must support WebRTC for camera access
- Minimum screen size for QR display: 10 inches
- Face recognition requires adequate lighting

### Business Constraints
- One attendance per student per session
- Session must be active for attendance marking
- Face verification must complete before QR scan
- QR codes expire after 45 seconds
- Maximum 3 face verification attempts

### Performance Constraints
- Face verification: < 3 seconds
- QR validation: < 1 second
- Real-time update latency: < 2 seconds
- Support 100+ concurrent students per session
- Database query response: < 500ms

---

## 1.9 Assumptions

1. All students have access to devices with cameras
2. Classroom has stable internet connectivity
3. Instructor has a display device for QR code
4. Students are within physical proximity to scan QR
5. Adequate lighting available for face capture
6. Students register face data before first attendance
7. One instructor per session
8. Students belong to registered classes

---

## 1.10 Success Criteria

The system is considered successful when:

### Functional Success
- ✓ Instructors can start/stop sessions
- ✓ QR codes auto-refresh every 45 seconds
- ✓ Students can verify face successfully
- ✓ Students can scan QR and mark attendance
- ✓ Attendance marked only when both verifications pass
- ✓ Old/expired QR codes are rejected
- ✓ Duplicate attendance is prevented
- ✓ Real-time updates work correctly

### Performance Success
- ✓ Face verification completes in < 3 seconds
- ✓ System supports 100+ concurrent users
- ✓ 99.9% uptime during class hours
- ✓ < 1% false acceptance rate
- ✓ < 5% false rejection rate

### Security Success
- ✓ Screenshot attacks prevented
- ✓ Replay attacks prevented
- ✓ Proxy attendance prevented
- ✓ All validations enforced on backend
- ✓ No security vulnerabilities

### User Satisfaction
- ✓ 90%+ instructor satisfaction
- ✓ 85%+ student satisfaction
- ✓ < 5% support requests
- ✓ Faster than manual attendance

---

## 1.11 High-Level Workflow

### Instructor Workflow
```
Login → Dashboard → Start Session → Display QR → Monitor Attendance → Stop Session → View Report
```

### Student Workflow
```
Login → Mark Attendance → Verify Face → Scan QR → Confirmation → View History
```

### System Workflow
```
Session Created → QR Generated → Auto-Refresh (45s) → Student Verifies → Backend Validates → Attendance Marked → Notify Instructor
```

---

## 1.12 Technology Overview

### Frontend
- React.js / Vue.js
- HTML5 Camera API
- QR Scanner Library
- WebSocket Client
- Responsive Design

### Backend
- Node.js + Express.js
- MongoDB Database
- JWT Authentication
- Socket.io (WebSocket)
- RESTful APIs

### Face Recognition
- Python (Flask/FastAPI)
- TensorFlow/PyTorch
- FaceNet/DeepFace
- OpenCV
- MTCNN Face Detector

### Infrastructure
- Cloud hosting (AWS/Azure/GCP)
- HTTPS/SSL
- Load balancing
- Database replication

---

## 1.13 Document Structure

This Software Design Document is organized into multiple files:

- **0001_system_overview.md** - This document
- **0002_architecture.md** - System architecture and components
- **0003_instructor_app.md** - Instructor web app design
- **0004_student_app.md** - Student web app design
- **0005_face_recognition.md** - Face recognition module
- **0006_qr_system.md** - QR code system design
- **0007_database_schema.md** - Database design
- **0008_api_specifications.md** - API endpoints
- **0009_security_design.md** - Security architecture
- **0010_business_rules.md** - Business logic and rules
- **0011_deployment.md** - Deployment architecture
- **0012_testing_strategy.md** - Testing approach
- **0013_future_enhancements.md** - Future improvements

---

## 1.14 Glossary

**Session**: A time-bound attendance period for a specific class  
**QR Token**: Cryptographically signed data encoded in QR code  
**Embedding**: Numerical vector representation of a face  
**Similarity**: Measure of how close two face embeddings are  
**Threshold**: Minimum similarity required for face match  
**Verification**: Process of confirming student identity  
**Validation**: Backend checks before marking attendance  
**WebSocket**: Real-time bidirectional communication protocol  
**JWT**: JSON Web Token for authentication  
**Nonce**: Random unique value to prevent replay attacks

