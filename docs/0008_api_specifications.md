# API Specifications
# RESTful API Endpoints

---

## 8.1 API Overview

**Base URL:** `https://api.attendance-system.com/api`

**Authentication:** JWT Bearer Token

**Content-Type:** `application/json`

**Response Format:** JSON

---

## 8.2 Authentication APIs

### 8.2.1 Register User

**Endpoint:** `POST /auth/register`

**Description:** Register new user (instructor or student)

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123",
  "role": "student",
  "name": "John Doe",
  "rollNumber": "CS2026001",
  "department": "Computer Science",
  "phone": "+1234567890"
}
```

**Response (Success - 201):**
```json
{
  "success": true,
  "message": "User registered successfully",
  "user": {
    "id": "65f8a1b2c3d4e5f6a7b8c9d2",
    "email": "user@example.com",
    "role": "student",
    "name": "John Doe"
  }
}
```

**Response (Error - 400):**
```json
{
  "success": false,
  "error": "Email already exists"
}
```

---

### 8.2.2 Login

**Endpoint:** `POST /auth/login`

**Description:** Authenticate user and get JWT token

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123",
  "role": "student"
}
```

**Response (Success - 200):**
```json
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "65f8a1b2c3d4e5f6a7b8c9d2",
    "email": "user@example.com",
    "role": "student",
    "name": "John Doe",
    "rollNumber": "CS2026001"
  }
}
```

**Response (Error - 401):**
```json
{
  "success": false,
  "error": "Invalid credentials"
}
```

---

### 8.2.3 Verify Token

**Endpoint:** `GET /auth/verify`

**Description:** Verify if JWT token is valid

**Headers:**
```
Authorization: Bearer <token>
```

**Response (Success - 200):**
```json
{
  "valid": true,
  "user": {
    "id": "65f8a1b2c3d4e5f6a7b8c9d2",
    "email": "user@example.com",
    "role": "student"
  }
}
```

---

## 8.3 Instructor APIs

### 8.3.1 Start Session

**Endpoint:** `POST /instructor/session/start`

**Description:** Create and start new attendance session

**Headers:**
```
Authorization: Bearer <instructor_token>
```

**Request Body:**
```json
{
  "classId": "65f8a1b2c3d4e5f6a7b8c9d4",
  "className": "Computer Science 101",
  "subject": "Data Structures"
}
```

**Response (Success - 201):**
```json
{
  "success": true,
  "session": {
    "id": "65f8a1b2c3d4e5f6a7b8c9d3",
    "classId": "65f8a1b2c3d4e5f6a7b8c9d4",
    "className": "Computer Science 101",
    "subject": "Data Structures",
    "status": "active",
    "startTime": "2026-03-07T11:00:00Z",
    "qrToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "qrCode": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
    "qrExpiresAt": "2026-03-07T11:00:45Z"
  }
}
```

---

### 8.3.2 Stop Session

**Endpoint:** `POST /instructor/session/:sessionId/stop`

**Description:** Stop active attendance session

**Headers:**
```
Authorization: Bearer <instructor_token>
```

**Response (Success - 200):**
```json
{
  "success": true,
  "message": "Session stopped successfully",
  "session": {
    "id": "65f8a1b2c3d4e5f6a7b8c9d3",
    "status": "stopped",
    "startTime": "2026-03-07T11:00:00Z",
    "stopTime": "2026-03-07T11:50:00Z",
    "presentCount": 45,
    "totalStudents": 50
  }
}
```

---

### 8.3.3 Get Session Details

**Endpoint:** `GET /instructor/session/:sessionId`

**Description:** Get session information and attendance list

**Headers:**
```
Authorization: Bearer <instructor_token>
```

**Response (Success - 200):**
```json
{
  "success": true,
  "session": {
    "id": "65f8a1b2c3d4e5f6a7b8c9d3",
    "className": "Computer Science 101",
    "subject": "Data Structures",
    "status": "active",
    "startTime": "2026-03-07T11:00:00Z",
    "stopTime": null,
    "presentCount": 23,
    "totalStudents": 50
  },
  "attendance": [
    {
      "studentId": "65f8a1b2c3d4e5f6a7b8c9d2",
      "name": "Alice Smith",
      "rollNumber": "CS2026001",
      "markedAt": "2026-03-07T11:05:30Z",
      "confidence": 0.87
    },
    {
      "studentId": "65f8a1b2c3d4e5f6a7b8c9d7",
      "name": "Bob Johnson",
      "rollNumber": "CS2026002",
      "markedAt": "2026-03-07T11:06:15Z",
      "confidence": 0.92
    }
  ]
}
```

---

### 8.3.4 Get Current QR Code

**Endpoint:** `GET /instructor/session/:sessionId/qr`

**Description:** Get current valid QR code for session

**Headers:**
```
Authorization: Bearer <instructor_token>
```

**Response (Success - 200):**
```json
{
  "success": true,
  "qrCode": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expiresAt": 1709809245000
}
```

---

### 8.3.5 Get All Sessions

**Endpoint:** `GET /instructor/sessions`

**Description:** Get all sessions for instructor

**Headers:**
```
Authorization: Bearer <instructor_token>
```

**Query Parameters:**
- `status` (optional): Filter by status (active/stopped)
- `limit` (optional): Number of results (default: 50)
- `page` (optional): Page number (default: 1)

**Response (Success - 200):**
```json
{
  "success": true,
  "sessions": [
    {
      "id": "65f8a1b2c3d4e5f6a7b8c9d3",
      "className": "Computer Science 101",
      "subject": "Data Structures",
      "status": "active",
      "startTime": "2026-03-07T11:00:00Z",
      "presentCount": 23
    }
  ],
  "pagination": {
    "total": 100,
    "page": 1,
    "pages": 2
  }
}
```

---

## 8.4 Student APIs

### 8.4.1 Register Face

**Endpoint:** `POST /student/face/register`

**Description:** Register student face embeddings

**Headers:**
```
Authorization: Bearer <student_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "images": [
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA...",
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA...",
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA...",
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA...",
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA..."
  ]
}
```

**Response (Success - 200):**
```json
{
  "success": true,
  "message": "Face registered successfully",
  "imageCount": 5
}
```

**Response (Error - 400):**
```json
{
  "success": false,
  "error": "No face detected in one or more images"
}
```

---

### 8.4.2 Verify Face

**Endpoint:** `POST /student/face/verify`

**Description:** Verify student face for attendance

**Headers:**
```
Authorization: Bearer <student_token>
```

**Request Body:**
```json
{
  "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA..."
}
```

**Response (Success - 200):**
```json
{
  "verified": true,
  "confidence": 0.87,
  "message": "Face verified successfully"
}
```

**Response (Failure - 200):**
```json
{
  "verified": false,
  "confidence": 0.45,
  "reason": "Similarity below threshold"
}
```

---

### 8.4.3 Mark Attendance

**Endpoint:** `POST /student/attendance/mark`

**Description:** Mark attendance with QR token and face verification

**Headers:**
```
Authorization: Bearer <student_token>
```

**Request Body:**
```json
{
  "qrToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "faceVerified": true
}
```

**Response (Success - 200):**
```json
{
  "success": true,
  "message": "Attendance marked successfully",
  "attendance": {
    "sessionId": "65f8a1b2c3d4e5f6a7b8c9d3",
    "studentId": "65f8a1b2c3d4e5f6a7b8c9d2",
    "markedAt": "2026-03-07T11:05:30Z",
    "className": "Computer Science 101"
  }
}
```

**Response (Error - 400):**
```json
{
  "success": false,
  "error": "QR code has expired"
}
```

**Possible Error Messages:**
- "Invalid QR code signature"
- "QR code has expired"
- "Invalid session"
- "Session is not active"
- "QR code is outdated. Please scan the latest QR code."
- "Attendance already marked for this session"
- "Face verification required"

---

### 8.4.4 Get Attendance History

**Endpoint:** `GET /student/attendance/history`

**Description:** Get student's attendance history

**Headers:**
```
Authorization: Bearer <student_token>
```

**Query Parameters:**
- `limit` (optional): Number of results (default: 50)
- `page` (optional): Page number (default: 1)

**Response (Success - 200):**
```json
{
  "success": true,
  "attendance": [
    {
      "sessionId": "65f8a1b2c3d4e5f6a7b8c9d3",
      "className": "Computer Science 101",
      "subject": "Data Structures",
      "markedAt": "2026-03-07T11:05:30Z",
      "confidence": 0.87
    },
    {
      "sessionId": "65f8a1b2c3d4e5f6a7b8c9d8",
      "className": "Computer Science 101",
      "subject": "Algorithms",
      "markedAt": "2026-03-06T10:15:20Z",
      "confidence": 0.91
    }
  ],
  "statistics": {
    "totalSessions": 20,
    "attended": 18,
    "percentage": 90
  }
}
```

---

### 8.4.5 Get Attendance Status

**Endpoint:** `GET /student/attendance/status/:sessionId`

**Description:** Check if attendance marked for specific session

**Headers:**
```
Authorization: Bearer <student_token>
```

**Response (Success - 200):**
```json
{
  "success": true,
  "marked": true,
  "markedAt": "2026-03-07T11:05:30Z"
}
```

---

## 8.5 Class Management APIs

### 8.5.1 Get Classes (Instructor)

**Endpoint:** `GET /instructor/classes`

**Headers:**
```
Authorization: Bearer <instructor_token>
```

**Response (Success - 200):**
```json
{
  "success": true,
  "classes": [
    {
      "id": "65f8a1b2c3d4e5f6a7b8c9d4",
      "className": "Data Structures and Algorithms",
      "courseCode": "CS201",
      "department": "Computer Science",
      "studentCount": 50
    }
  ]
}
```

---

### 8.5.2 Get Classes (Student)

**Endpoint:** `GET /student/classes`

**Headers:**
```
Authorization: Bearer <student_token>
```

**Response (Success - 200):**
```json
{
  "success": true,
  "classes": [
    {
      "id": "65f8a1b2c3d4e5f6a7b8c9d4",
      "className": "Data Structures and Algorithms",
      "courseCode": "CS201",
      "instructorName": "Dr. John Doe",
      "schedule": [
        {
          "day": "Monday",
          "startTime": "10:00",
          "endTime": "11:30",
          "room": "Room 301"
        }
      ]
    }
  ]
}
```

---

## 8.6 Error Response Format

All error responses follow this format:

```json
{
  "success": false,
  "error": "Error message here",
  "code": "ERROR_CODE",
  "details": {}
}
```

**Common Error Codes:**

| Code | HTTP Status | Description |
|------|-------------|-------------|
| UNAUTHORIZED | 401 | Invalid or missing token |
| FORBIDDEN | 403 | Insufficient permissions |
| NOT_FOUND | 404 | Resource not found |
| VALIDATION_ERROR | 400 | Invalid request data |
| DUPLICATE_ENTRY | 409 | Resource already exists |
| SERVER_ERROR | 500 | Internal server error |

---

## 8.7 Rate Limiting

**Limits:**
- Authentication endpoints: 5 requests per minute
- Face verification: 10 requests per minute
- Attendance marking: 3 requests per minute
- Other endpoints: 60 requests per minute

**Rate Limit Headers:**
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1709809260
```

**Rate Limit Exceeded Response (429):**
```json
{
  "success": false,
  "error": "Rate limit exceeded",
  "retryAfter": 30
}
```

---

## 8.8 WebSocket Events

### 8.8.1 Connection

**URL:** `wss://api.attendance-system.com`

**Authentication:**
```javascript
socket.emit('authenticate', { token: 'jwt_token_here' });
```

### 8.8.2 Join Session Room

**Event:** `join_session`

**Payload:**
```javascript
{
  sessionId: "65f8a1b2c3d4e5f6a7b8c9d3"
}
```

### 8.8.3 QR Refresh Event

**Event:** `qr_refresh`

**Payload (Server → Client):**
```javascript
{
  sessionId: "65f8a1b2c3d4e5f6a7b8c9d3",
  qrCode: "data:image/png;base64,...",
  token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  expiresAt: 1709809245000
}
```

### 8.8.4 Attendance Marked Event

**Event:** `attendance_marked`

**Payload (Server → Client):**
```javascript
{
  sessionId: "65f8a1b2c3d4e5f6a7b8c9d3",
  student: {
    id: "65f8a1b2c3d4e5f6a7b8c9d2",
    name: "Alice Smith",
    rollNumber: "CS2026001"
  },
  markedAt: "2026-03-07T11:05:30Z",
  presentCount: 24
}
```

### 8.8.5 Session Status Event

**Event:** `session_status`

**Payload (Server → Client):**
```javascript
{
  sessionId: "65f8a1b2c3d4e5f6a7b8c9d3",
  status: "stopped",
  stopTime: "2026-03-07T11:50:00Z"
}
```

---

## 8.9 API Testing Examples

### 8.9.1 cURL Examples

**Login:**
```bash
curl -X POST https://api.attendance-system.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "student@example.com",
    "password": "password123",
    "role": "student"
  }'
```

**Mark Attendance:**
```bash
curl -X POST https://api.attendance-system.com/api/student/attendance/mark \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "qrToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "faceVerified": true
  }'
```

### 8.9.2 JavaScript Examples

**Using Axios:**
```javascript
// Login
const loginResponse = await axios.post('/api/auth/login', {
  email: 'student@example.com',
  password: 'password123',
  role: 'student'
});

const token = loginResponse.data.token;

// Mark Attendance
const attendanceResponse = await axios.post(
  '/api/student/attendance/mark',
  {
    qrToken: scannedToken,
    faceVerified: true
  },
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);
```

