# Business Rules and Validation Logic
# System Constraints and Business Requirements

---

## 10.1 Core Business Rules

### 10.1.1 Dual Verification Rule

**Rule:** Attendance can ONLY be marked when BOTH conditions are satisfied:
1. Face verification succeeds
2. Valid QR code is scanned

**Implementation:**
```javascript
async function markAttendance(studentId, qrToken, faceVerified) {
  // Rule enforcement
  if (!faceVerified) {
    throw new Error('Face verification required');
  }
  
  // Validate QR token
  const qrValidation = await validateQRToken(qrToken);
  if (!qrValidation.valid) {
    throw new Error(qrValidation.reason);
  }
  
  // Both conditions met - proceed
  // ... create attendance record
}
```

**Truth Table:**

| Face Verified | QR Valid | Attendance Marked |
|---------------|----------|-------------------|
| ✓ | ✓ | ✓ YES |
| ✓ | ✗ | ✗ NO |
| ✗ | ✓ | ✗ NO |
| ✗ | ✗ | ✗ NO |

---

## 10.2 Session Rules

### 10.2.1 Session Lifecycle

**States:**
- `active` - Session is running, attendance can be marked
- `stopped` - Session ended, no attendance allowed

**State Transitions:**
```
[Created] → Start Session → [Active] → Stop Session → [Stopped]
                                ↓
                         Mark Attendance
```

**Rule:** Once stopped, session cannot be reactivated

**Implementation:**
```javascript
async function stopSession(sessionId) {
  const session = await Session.findById(sessionId);
  
  if (session.status === 'stopped') {
    throw new Error('Session already stopped');
  }
  
  // Stop session
  await Session.updateOne(
    { _id: sessionId },
    {
      status: 'stopped',
      stopTime: new Date(),
      currentQRToken: null  // Invalidate QR
    }
  );
}
```

### 10.2.2 Active Session Rule

**Rule:** Attendance can only be marked during active sessions

**Validation:**
```javascript
async function validateSessionActive(sessionId) {
  const session = await Session.findById(sessionId);
  
  if (!session) {
    throw new Error('Session not found');
  }
  
  if (session.status !== 'active') {
    throw new Error('Session is not active');
  }
  
  return session;
}
```

### 10.2.3 One Session Per Class Rule

**Rule:** Instructor can have only ONE active session per class at a time

**Validation:**
```javascript
async function startSession(instructorId, classId) {
  // Check for existing active session
  const existingSession = await Session.findOne({
    instructorId: instructorId,
    classId: classId,
    status: 'active'
  });
  
  if (existingSession) {
    throw new Error('An active session already exists for this class');
  }
  
  // Create new session
  // ...
}
```

---

## 10.3 QR Code Rules

### 10.3.1 QR Expiration Rule

**Rule:** QR codes expire after exactly 45 seconds

**Implementation:**
```javascript
function generateQRToken(sessionId, instructorId) {
  const now = Date.now();
  
  const payload = {
    sessionId: sessionId,
    instructorId: instructorId,
    timestamp: now,
    expiresAt: now + 45000,  // 45 seconds
    nonce: generateNonce()
  };
  
  return jwt.sign(payload, SECRET_KEY);
}

function validateExpiration(token) {
  const decoded = jwt.verify(token, SECRET_KEY);
  
  if (Date.now() > decoded.expiresAt) {
    throw new Error('QR code has expired');
  }
  
  return decoded;
}
```

### 10.3.2 QR Auto-Refresh Rule

**Rule:** QR codes must auto-refresh every 45 seconds for active sessions

**Implementation:**
```javascript
// Runs every 45 seconds
setInterval(async () => {
  const activeSessions = await Session.find({ status: 'active' });
  
  for (const session of activeSessions) {
    const newToken = generateQRToken(session._id, session.instructorId);
    
    await Session.updateOne(
      { _id: session._id },
      {
        currentQRToken: newToken,
        qrExpiresAt: new Date(Date.now() + 45000)
      }
    );
    
    // Broadcast to instructor
    io.to(`session_${session._id}`).emit('qr_refresh', {
      token: newToken
    });
  }
}, 45000);
```

### 10.3.3 QR Currency Rule

**Rule:** Only the CURRENT QR token is valid; old tokens are rejected

**Validation:**
```javascript
async function validateQRCurrency(token, sessionId) {
  const session = await Session.findById(sessionId);
  
  if (session.currentQRToken !== token) {
    throw new Error('QR code is outdated. Please scan the latest QR code.');
  }
  
  return true;
}
```

### 10.3.4 QR Invalidation on Stop Rule

**Rule:** When session stops, current QR token becomes invalid immediately

**Implementation:**
```javascript
async function stopSession(sessionId) {
  await Session.updateOne(
    { _id: sessionId },
    {
      status: 'stopped',
      stopTime: new Date(),
      currentQRToken: null,  // Invalidate
      qrExpiresAt: null
    }
  );
}
```

---

## 10.4 Attendance Rules

### 10.4.1 One Attendance Per Session Rule

**Rule:** A student can mark attendance only ONCE per session

**Validation:**
```javascript
async function checkDuplicateAttendance(studentId, sessionId) {
  const existing = await Attendance.findOne({
    studentId: studentId,
    sessionId: sessionId
  });
  
  if (existing) {
    throw new Error('Attendance already marked for this session');
  }
  
  return true;
}
```

**Database Enforcement:**
```javascript
// Compound unique index
attendanceSchema.index(
  { sessionId: 1, studentId: 1 }, 
  { unique: true }
);
```

### 10.4.2 Sequential Verification Rule

**Rule:** Face verification MUST complete before QR scanning

**Frontend Enforcement:**
```javascript
function AttendanceFlow() {
  const [step, setStep] = useState('face');
  const [faceVerified, setFaceVerified] = useState(false);
  
  function handleFaceVerified() {
    setFaceVerified(true);
    setStep('qr');  // Enable QR scanner only after face verified
  }
  
  return (
    <div>
      {step === 'face' && <FaceVerification onSuccess={handleFaceVerified} />}
      {step === 'qr' && faceVerified && <QRScanner />}
    </div>
  );
}
```

**Backend Enforcement:**
```javascript
async function markAttendance(studentId, qrToken, faceVerified) {
  if (!faceVerified) {
    throw new Error('Face verification must be completed first');
  }
  
  // Proceed with QR validation
  // ...
}
```

### 10.4.3 Attendance Timestamp Rule

**Rule:** Attendance timestamp is server-generated, not client-provided

**Implementation:**
```javascript
async function createAttendanceRecord(studentId, sessionId) {
  const attendance = await Attendance.create({
    studentId: studentId,
    sessionId: sessionId,
    markedAt: new Date(),  // Server timestamp
    faceVerified: true,
    qrVerified: true
  });
  
  return attendance;
}
```

---

## 10.5 Face Recognition Rules

### 10.5.1 Minimum Images Rule

**Rule:** Students must register minimum 3 face images

**Validation:**
```javascript
async function registerFace(studentId, images) {
  if (images.length < 3) {
    throw new Error('Minimum 3 images required for face registration');
  }
  
  if (images.length > 10) {
    throw new Error('Maximum 10 images allowed');
  }
  
  // Process images
  // ...
}
```

### 10.5.2 Face Detection Rule

**Rule:** All registration images must contain detectable faces

**Validation:**
```python
def register_face(student_id, images):
    embeddings = []
    
    for img in images:
        face = detect_face(img)
        
        if face is None:
            raise ValueError("No face detected in one or more images")
        
        embedding = extract_embedding(face)
        embeddings.append(embedding)
    
    # Store embeddings
    store_embeddings(student_id, embeddings)
```

### 10.5.3 Similarity Threshold Rule

**Rule:** Face match requires similarity ≥ 0.6 (configurable)

**Implementation:**
```python
THRESHOLD = 0.6

def verify_face(student_id, live_image):
    live_embedding = extract_embedding(live_image)
    stored_embeddings = get_embeddings(student_id)
    
    similarities = [
        cosine_similarity(live_embedding, stored)
        for stored in stored_embeddings
    ]
    
    max_similarity = max(similarities)
    
    if max_similarity >= THRESHOLD:
        return {
            'verified': True,
            'confidence': max_similarity
        }
    else:
        return {
            'verified': False,
            'confidence': max_similarity,
            'reason': 'Similarity below threshold'
        }
```

### 10.5.4 Retry Limit Rule

**Rule:** Maximum 3 face verification attempts per attendance attempt

**Implementation:**
```javascript
const verificationAttempts = new Map();

async function verifyFaceWithLimit(studentId) {
  const key = `${studentId}_${Date.now()}`;
  const attempts = verificationAttempts.get(key) || 0;
  
  if (attempts >= 3) {
    throw new Error('Maximum verification attempts exceeded');
  }
  
  verificationAttempts.set(key, attempts + 1);
  
  // Perform verification
  // ...
  
  // Clear after 5 minutes
  setTimeout(() => {
    verificationAttempts.delete(key);
  }, 300000);
}
```

---

## 10.6 User Rules

### 10.6.1 Email Uniqueness Rule

**Rule:** Each email can be registered only once

**Database Enforcement:**
```javascript
userSchema.index({ email: 1 }, { unique: true });
```

**Application Validation:**
```javascript
async function registerUser(email, password, role) {
  const existing = await User.findOne({ email: email });
  
  if (existing) {
    throw new Error('Email already registered');
  }
  
  // Create user
  // ...
}
```

### 10.6.2 Roll Number Uniqueness Rule

**Rule:** Each student roll number must be unique

**Database Enforcement:**
```javascript
userSchema.index({ rollNumber: 1 }, { unique: true, sparse: true });
```

### 10.6.3 Role Restriction Rule

**Rule:** Users can only have role 'instructor' or 'student'

**Validation:**
```javascript
userSchema.path('role').validate(function(value) {
  return ['instructor', 'student'].includes(value);
}, 'Invalid role');
```

---

## 10.7 Class Rules

### 10.7.1 Student Enrollment Rule

**Rule:** Students can only mark attendance for classes they're enrolled in

**Validation:**
```javascript
async function validateEnrollment(studentId, classId) {
  const classData = await Class.findById(classId);
  
  if (!classData) {
    throw new Error('Class not found');
  }
  
  const isEnrolled = classData.students.some(
    id => id.toString() === studentId
  );
  
  if (!isEnrolled) {
    throw new Error('You are not enrolled in this class');
  }
  
  return true;
}
```

### 10.7.2 Instructor Ownership Rule

**Rule:** Only the assigned instructor can manage class sessions

**Validation:**
```javascript
async function validateInstructorOwnership(instructorId, classId) {
  const classData = await Class.findById(classId);
  
  if (classData.instructorId.toString() !== instructorId) {
    throw new Error('You are not the instructor for this class');
  }
  
  return true;
}
```

---

## 10.8 Validation Flow

### 10.8.1 Complete Attendance Validation

```javascript
async function validateAndMarkAttendance(studentId, qrToken, faceVerified) {
  // Validation 1: Face verification
  if (!faceVerified) {
    throw new Error('Face verification required');
  }
  
  // Validation 2: JWT signature
  let decoded;
  try {
    decoded = jwt.verify(qrToken, SECRET_KEY);
  } catch (error) {
    throw new Error('Invalid QR code signature');
  }
  
  // Validation 3: Token expiration
  if (Date.now() > decoded.expiresAt) {
    throw new Error('QR code has expired');
  }
  
  // Validation 4: Session exists
  const session = await Session.findById(decoded.sessionId);
  if (!session) {
    throw new Error('Invalid session');
  }
  
  // Validation 5: Session active
  if (session.status !== 'active') {
    throw new Error('Session is not active');
  }
  
  // Validation 6: QR currency
  if (session.currentQRToken !== qrToken) {
    throw new Error('QR code is outdated');
  }
  
  // Validation 7: Enrollment check
  await validateEnrollment(studentId, session.classId);
  
  // Validation 8: Duplicate check
  const existing = await Attendance.findOne({
    sessionId: decoded.sessionId,
    studentId: studentId
  });
  
  if (existing) {
    throw new Error('Attendance already marked');
  }
  
  // All validations passed - create record
  const attendance = await Attendance.create({
    sessionId: decoded.sessionId,
    studentId: studentId,
    markedAt: new Date(),
    faceVerified: true,
    qrVerified: true
  });
  
  // Update session count
  await Session.updateOne(
    { _id: decoded.sessionId },
    { $inc: { presentCount: 1 } }
  );
  
  // Notify instructor
  io.to(`session_${decoded.sessionId}`).emit('attendance_marked', {
    studentId: studentId,
    markedAt: attendance.markedAt
  });
  
  return attendance;
}
```

---

## 10.9 Error Messages

### 10.9.1 Standardized Error Messages

| Error Condition | Error Message |
|----------------|---------------|
| Face not verified | "Face verification required" |
| Invalid QR signature | "Invalid QR code signature" |
| QR expired | "QR code has expired" |
| QR outdated | "QR code is outdated. Please scan the latest QR code." |
| Session not found | "Invalid session" |
| Session stopped | "Session is not active" |
| Already marked | "Attendance already marked for this session" |
| Not enrolled | "You are not enrolled in this class" |
| Max attempts | "Maximum verification attempts exceeded" |

### 10.9.2 Error Response Format

```javascript
{
  "success": false,
  "error": "QR code has expired",
  "code": "QR_EXPIRED",
  "action": "scan_new_qr",
  "timestamp": "2026-03-07T11:05:30Z"
}
```

---

## 10.10 Business Constraints

### 10.10.1 Time Constraints

- QR expiration: 45 seconds (fixed)
- QR refresh interval: 45 seconds (fixed)
- JWT token expiration: 24 hours
- Session duration: No limit (manual stop)
- Face verification timeout: 30 seconds

### 10.10.2 Quantity Constraints

- Minimum face images: 3
- Maximum face images: 10
- Maximum retry attempts: 3
- Maximum active sessions per instructor: Unlimited
- Maximum students per class: Unlimited

### 10.10.3 Data Constraints

- Email: Valid email format, max 255 characters
- Password: Min 8 characters, max 128 characters
- Name: Min 2 characters, max 100 characters
- Roll number: Max 50 characters
- Face embedding dimension: 512 (fixed)

---

## 10.11 Business Logic Summary

**Attendance Marking Prerequisites:**
1. ✓ Student registered in system
2. ✓ Student enrolled in class
3. ✓ Student face data registered
4. ✓ Session is active
5. ✓ Face verification succeeds
6. ✓ QR code is valid and current
7. ✓ No duplicate attendance exists

**Validation Order:**
1. Face verification status
2. JWT signature verification
3. Token expiration check
4. Session existence check
5. Session status check
6. QR currency check
7. Enrollment verification
8. Duplicate attendance check

**Success Criteria:**
- All 8 validations pass
- Attendance record created
- Session count incremented
- Instructor notified
- Student receives confirmation

