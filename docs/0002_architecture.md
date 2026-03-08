# System Architecture
# High-Level Architecture and Component Design

---

## 2.1 Architecture Overview

The system follows a **three-tier architecture** with clear separation of concerns:

1. **Presentation Layer**: Instructor and Student web applications
2. **Application Layer**: Backend API server and business logic
3. **Data Layer**: MongoDB database and face embeddings storage

---

## 2.2 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                            │
├─────────────────────────────────┬───────────────────────────────────┤
│     Instructor Web App          │        Student Web App            │
│     (React/Vue.js)              │        (React/Vue.js)             │
│                                 │                                   │
│  • Session Management UI        │  • Face Capture UI                │
│  • QR Display Component         │  • QR Scanner Component           │
│  • Live Attendance Dashboard    │  • Attendance History UI          │
│  • Real-time Updates            │  • Profile Management             │
└─────────────┬───────────────────┴──────────────┬────────────────────┘
              │                                  │
              │         HTTPS/WSS                │
              │                                  │
┌─────────────┴──────────────────────────────────┴────────────────────┐
│                        APPLICATION LAYER                             │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │              Backend API Server (Node.js + Express)        │    │
│  │                                                            │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐ │    │
│  │  │ Auth Service │  │Session Service│  │Attendance Service│ │    │
│  │  └──────────────┘  └──────────────┘  └─────────────────┘ │    │
│  │                                                            │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐ │    │
│  │  │  QR Service  │  │ Face Service │  │ WebSocket Server│ │    │
│  │  └──────────────┘  └──────────────┘  └─────────────────┘ │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │         Face Recognition Service (Python + Flask)          │    │
│  │                                                            │    │
│  │  • Face Detection (MTCNN)                                 │    │
│  │  • Embedding Extraction (FaceNet)                         │    │
│  │  • Similarity Computation                                 │    │
│  │  • Verification Logic                                     │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │              QR Refresh Service (Node.js)                  │    │
│  │                                                            │    │
│  │  • Monitor Active Sessions                                │    │
│  │  • Generate New Tokens (Every 45s)                        │    │
│  │  • Update Database                                        │    │
│  │  • Broadcast via WebSocket                                │    │
│  └────────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
┌──────────────────────────────┴───────────────────────────────────────┐
│                           DATA LAYER                                 │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                    MongoDB Database                        │    │
│  │                                                            │    │
│  │  Collections:                                             │    │
│  │  • users          - User accounts (instructors, students) │    │
│  │  • sessions       - Attendance sessions                   │    │
│  │  • attendance     - Attendance records                    │    │
│  │  • face_data      - Face embeddings                       │    │
│  │  • classes        - Class/course information              │    │
│  └────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2.3 Component Descriptions

### 2.3.1 Instructor Web App

**Technology Stack:**
- React.js 18+ or Vue.js 3+
- Axios for HTTP requests
- Socket.io-client for WebSocket
- QRCode.js for QR generation
- TailwindCSS / Material-UI for styling

**Key Components:**

**LoginComponent**
- Email/password input
- Form validation
- JWT token storage
- Role verification

**DashboardComponent**
- Session list view
- Quick actions (start session)
- Statistics overview
- Navigation menu

**SessionComponent**
- Session details display
- Start/Stop buttons
- QR code display area
- Session status indicator
- Timer display

**QRDisplayComponent**
- QR code rendering
- Auto-refresh listener
- Expiration countdown
- Full-screen mode

**AttendanceListComponent**
- Real-time student list
- Attendance status indicators
- Search/filter functionality
- Export options

**WebSocketManager**
- Connection management
- Event listeners (qr_refresh, attendance_marked)
- Reconnection logic
- Error handling

---

### 2.3.2 Student Web App

**Technology Stack:**
- React.js 18+ or Vue.js 3+
- Axios for HTTP requests
- html5-qrcode for QR scanning
- face-api.js or custom face capture
- Webcam library for camera access

**Key Components:**

**LoginComponent**
- Email/password input
- Form validation
- JWT token storage

**ProfileComponent**
- Student information display
- Face registration option
- Attendance statistics

**FaceVerificationComponent**
- Camera feed display
- Capture button
- Face detection overlay
- Verification status
- Retry mechanism

**QRScannerComponent**
- Camera feed for QR scanning
- QR detection and decoding
- Scan result display
- Error handling

**AttendanceFlowComponent**
- Step-by-step wizard
- Progress indicator
- Face verification step
- QR scan step
- Confirmation step

**AttendanceHistoryComponent**
- List of past attendance
- Date filtering
- Session details
- Attendance percentage

---

### 2.3.3 Backend API Server

**Technology Stack:**
- Node.js 18+
- Express.js 4+
- Mongoose (MongoDB ODM)
- jsonwebtoken for JWT
- bcryptjs for password hashing
- Socket.io for WebSocket
- qrcode library
- cors middleware

**Service Architecture:**

**AuthService**
```javascript
class AuthService {
  async register(userData)
  async login(email, password, role)
  async verifyToken(token)
  async refreshToken(token)
  generateJWT(userId, role)
}
```

**SessionService**
```javascript
class SessionService {
  async createSession(instructorId, sessionData)
  async startSession(sessionId)
  async stopSession(sessionId)
  async getSessionById(sessionId)
  async getActiveSessions()
  async getSessionAttendance(sessionId)
}
```

**QRTokenService**
```javascript
class QRTokenService {
  generateToken(sessionId, instructorId)
  verifyToken(token)
  isTokenExpired(token)
  isTokenCurrent(token, sessionId)
}
```

**AttendanceService**
```javascript
class AttendanceService {
  async markAttendance(studentId, sessionId, qrToken)
  async validateAttendance(studentId, sessionId, qrToken)
  async checkDuplicate(studentId, sessionId)
  async getStudentAttendance(studentId)
  async getSessionAttendance(sessionId)
}
```

**FaceService**
```javascript
class FaceService {
  async registerFace(studentId, images)
  async verifyFace(studentId, image)
  async updateFaceData(studentId, images)
  callFaceRecognitionAPI(endpoint, data)
}
```

**WebSocketService**
```javascript
class WebSocketService {
  initialize(server)
  joinSessionRoom(socket, sessionId)
  emitQRRefresh(sessionId, token)
  emitAttendanceMarked(sessionId, studentData)
  broadcastSessionStatus(sessionId, status)
}
```

---

### 2.3.4 Face Recognition Service

**Technology Stack:**
- Python 3.9+
- Flask or FastAPI
- TensorFlow 2.x or PyTorch
- OpenCV
- MTCNN for face detection
- FaceNet or DeepFace for embeddings
- NumPy for computations

**Service Structure:**

```python
class FaceRecognitionService:
    def __init__(self):
        self.detector = MTCNN()
        self.embedder = FaceNet()
    
    def detect_face(self, image)
    def extract_embedding(self, face_image)
    def compare_embeddings(self, embedding1, embedding2)
    def verify_identity(self, student_id, live_image)
    def register_face(self, student_id, images)
```

**API Endpoints:**
- `POST /face/register` - Register face embeddings
- `POST /face/verify` - Verify face against stored data
- `POST /face/detect` - Detect face in image
- `POST /face/extract` - Extract embedding from image

---

### 2.3.5 QR Refresh Service

**Technology Stack:**
- Node.js
- node-cron or setInterval
- MongoDB connection
- Socket.io client

**Service Logic:**

```javascript
class QRRefreshService {
  constructor() {
    this.interval = 45000; // 45 seconds
    this.timer = null;
  }
  
  start() {
    this.timer = setInterval(() => {
      this.refreshQRCodes();
    }, this.interval);
  }
  
  async refreshQRCodes() {
    // Get all active sessions
    const activeSessions = await Session.find({ status: 'active' });
    
    for (const session of activeSessions) {
      // Generate new token
      const newToken = QRTokenService.generateToken(
        session._id,
        session.instructorId
      );
      
      // Update session
      await Session.updateOne(
        { _id: session._id },
        {
          currentQRToken: newToken,
          qrExpiresAt: new Date(Date.now() + 45000)
        }
      );
      
      // Broadcast to instructor
      WebSocketService.emitQRRefresh(session._id, newToken);
    }
  }
  
  stop() {
    if (this.timer) {
      clearInterval(this.timer);
    }
  }
}
```

---

## 2.4 Communication Flow

### 2.4.1 Session Start Flow

```
Instructor App                Backend API              Database
      |                           |                        |
      |--[POST /session/start]--->|                        |
      |                           |---[Create Session]---->|
      |                           |<--[Session Created]----|
      |                           |                        |
      |                           |--[Generate QR Token]   |
      |                           |                        |
      |<--[Session + QR Token]----|                        |
      |                           |                        |
      |--[Join WebSocket Room]--->|                        |
      |                           |                        |
      
QR Refresh Service starts monitoring this session
```

### 2.4.2 QR Refresh Flow

```
QR Refresh Service         Database            WebSocket Server      Instructor App
      |                       |                       |                    |
      |--[Timer Trigger]      |                       |                    |
      |                       |                       |                    |
      |--[Get Active]-------->|                       |                    |
      |<--[Sessions]----------|                       |                    |
      |                       |                       |                    |
      |--[Generate New Token] |                       |                    |
      |                       |                       |                    |
      |--[Update Session]---->|                       |                    |
      |<--[Updated]-----------|                       |                    |
      |                       |                       |                    |
      |--[Emit qr_refresh]--->|--[Broadcast]--------->|--[Update QR]------>|
```

### 2.4.3 Attendance Marking Flow

```
Student App        Backend API       Face Service      Database      WebSocket
    |                  |                  |               |              |
    |--[Capture Face]  |                  |               |              |
    |                  |                  |               |              |
    |--[POST /verify]->|                  |               |              |
    |                  |--[Verify Face]-->|               |              |
    |                  |<--[Verified]-----|               |              |
    |<--[Success]------|                  |               |              |
    |                  |                  |               |              |
    |--[Scan QR]       |                  |               |              |
    |                  |                  |               |              |
    |--[POST /mark]--->|                  |               |              |
    |                  |--[Validate All]  |               |              |
    |                  |                  |               |              |
    |                  |--[Check Session]---------------->|              |
    |                  |<--[Active]----------------------|              |
    |                  |                  |               |              |
    |                  |--[Check Duplicate]-------------->|              |
    |                  |<--[Not Found]-------------------|              |
    |                  |                  |               |              |
    |                  |--[Create Record]---------------->|              |
    |                  |<--[Created]---------------------|              |
    |                  |                  |               |              |
    |                  |--[Notify]--------------------------->|          |
    |                  |                  |               |   |--[Emit]->|
    |<--[Success]------|                  |               |              |
```

---

## 2.5 Data Flow Architecture

### 2.5.1 Authentication Flow

```
User Input → Frontend Validation → API Request → Backend Validation
→ Database Query → Password Verification → JWT Generation → Response
→ Token Storage → Authenticated State
```

### 2.5.2 Face Registration Flow

```
Camera Capture → Multiple Images → Frontend Upload → Backend Receive
→ Face Service API → Face Detection → Embedding Extraction
→ Embedding Storage → Database Save → Confirmation Response
```

### 2.5.3 Attendance Validation Flow

```
QR Token + Face Verified → Backend Receive → JWT Verify → Timestamp Check
→ Session Status Check → Token Currency Check → Duplicate Check
→ All Pass? → Create Record → Notify Instructor → Confirm Student
```

---

## 2.6 Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React.js / Vue.js | UI framework |
| Frontend | Axios | HTTP client |
| Frontend | Socket.io-client | WebSocket client |
| Frontend | html5-qrcode | QR scanning |
| Frontend | Webcam API | Camera access |
| Backend | Node.js + Express | API server |
| Backend | MongoDB + Mongoose | Database |
| Backend | JWT | Authentication |
| Backend | Socket.io | WebSocket server |
| Backend | bcryptjs | Password hashing |
| Face Service | Python + Flask | Face recognition API |
| Face Service | TensorFlow/PyTorch | Deep learning |
| Face Service | FaceNet | Embedding model |
| Face Service | MTCNN | Face detection |
| Face Service | OpenCV | Image processing |
| Infrastructure | HTTPS/SSL | Secure communication |
| Infrastructure | Docker | Containerization |
| Infrastructure | Nginx | Reverse proxy |

---

## 2.7 Scalability Considerations

### Horizontal Scaling
- Multiple backend API instances behind load balancer
- Stateless API design for easy scaling
- WebSocket sticky sessions for connection persistence

### Database Scaling
- MongoDB replica sets for high availability
- Sharding for large datasets
- Indexing on frequently queried fields

### Caching Strategy
- Redis for session data caching
- In-memory embedding cache
- CDN for static assets

### Performance Optimization
- Database connection pooling
- Batch processing for embeddings
- Lazy loading in frontend
- Image compression for face data

