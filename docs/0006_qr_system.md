# QR Code System Design
# Dynamic QR Token Generation and Validation

---

## 6.1 QR System Overview

The QR code system is the **location verification** component of the attendance system. It ensures students are physically present in the classroom by requiring them to scan a QR code displayed on the instructor's screen.

**Key Features:**
- Auto-refresh every 45 seconds
- Cryptographically signed tokens
- Session-specific codes
- Prevents screenshot attacks
- Prevents replay attacks

---

## 6.2 QR Token Structure

### 6.2.1 Token Payload

The QR code contains a **JWT (JSON Web Token)** with the following payload:

```javascript
{
  sessionId: "65f8a1b2c3d4e5f6a7b8c9d0",
  instructorId: "65f8a1b2c3d4e5f6a7b8c9d1",
  timestamp: 1709809200000,
  expiresAt: 1709809245000,  // timestamp + 45 seconds
  nonce: "a1b2c3d4e5f6g7h8"  // random unique string
}
```

**Field Descriptions:**

| Field | Type | Purpose |
|-------|------|---------|
| sessionId | String | Links token to specific session |
| instructorId | String | Identifies session owner |
| timestamp | Number | Token creation time (Unix ms) |
| expiresAt | Number | Token expiration time (Unix ms) |
| nonce | String | Random value to prevent replay attacks |

### 6.2.2 JWT Signing

The payload is signed using **HS256 algorithm** with a secret key:

```javascript
const jwt = require('jsonwebtoken');

const SECRET_KEY = process.env.JWT_SECRET; // Strong secret key

function generateQRToken(sessionId, instructorId) {
  const now = Date.now();
  
  const payload = {
    sessionId: sessionId,
    instructorId: instructorId,
    timestamp: now,
    expiresAt: now + 45000, // 45 seconds
    nonce: generateNonce()
  };
  
  const token = jwt.sign(payload, SECRET_KEY, {
    algorithm: 'HS256'
  });
  
  return token;
}

function generateNonce() {
  // Generate random 16-character string
  return require('crypto').randomBytes(8).toString('hex');
}
```

**Example Token:**
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzZXNzaW9uSWQiOiI2NWY4YTFiMmMzZDRlNWY2YTdiOGM5ZDAiLCJpbnN0cnVjdG9ySWQiOiI2NWY4YTFiMmMzZDRlNWY2YTdiOGM5ZDEiLCJ0aW1lc3RhbXAiOjE3MDk4MDkyMDAwMDAsImV4cGlyZXNBdCI6MTcwOTgwOTI0NTAwMCwibm9uY2UiOiJhMWIyYzNkNGU1ZjZnN2g4In0.xyz123abc456def789
```

---

## 6.3 QR Code Generation

### 6.3.1 Backend Generation

```javascript
const QRCode = require('qrcode');

async function generateQRCode(token) {
  try {
    // Generate QR code as data URL
    const qrDataURL = await QRCode.toDataURL(token, {
      errorCorrectionLevel: 'M',
      type: 'image/png',
      width: 400,
      margin: 2,
      color: {
        dark: '#000000',
        light: '#FFFFFF'
      }
    });
    
    return qrDataURL;
  } catch (error) {
    throw new Error('Failed to generate QR code');
  }
}
```

### 6.3.2 Frontend Display

**React Component:**
```javascript
import React, { useState, useEffect } from 'react';

function QRDisplay({ sessionId }) {
  const [qrCode, setQrCode] = useState(null);
  const [expiresAt, setExpiresAt] = useState(null);
  const [timeLeft, setTimeLeft] = useState(45);
  
  useEffect(() => {
    // Fetch initial QR code
    fetchQRCode();
    
    // Listen for QR refresh via WebSocket
    socket.on('qr_refresh', (data) => {
      if (data.sessionId === sessionId) {
        setQrCode(data.qrCode);
        setExpiresAt(data.expiresAt);
        setTimeLeft(45);
      }
    });
    
    return () => {
      socket.off('qr_refresh');
    };
  }, [sessionId]);
  
  useEffect(() => {
    // Countdown timer
    const timer = setInterval(() => {
      setTimeLeft(prev => Math.max(0, prev - 1));
    }, 1000);
    
    return () => clearInterval(timer);
  }, [expiresAt]);
  
  async function fetchQRCode() {
    const response = await fetch(`/api/instructor/session/${sessionId}/qr`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    const data = await response.json();
    setQrCode(data.qrCode);
    setExpiresAt(data.expiresAt);
    setTimeLeft(45);
  }
  
  return (
    <div className="qr-display">
      <h3>Scan QR Code to Mark Attendance</h3>
      
      {qrCode && (
        <img src={qrCode} alt="QR Code" className="qr-image" />
      )}
      
      <div className="qr-timer">
        <p>Refreshes in: {timeLeft} seconds</p>
        <div className="progress-bar">
          <div 
            className="progress" 
            style={{ width: `${(timeLeft / 45) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}
```

---

## 6.4 QR Auto-Refresh System

### 6.4.1 Refresh Service Architecture

```
┌─────────────────────────────────────────────────────────┐
│              QR REFRESH SERVICE                         │
│                                                         │
│  Timer (Every 45 seconds)                              │
│         │                                               │
│         ▼                                               │
│  Find Active Sessions                                   │
│         │                                               │
│         ▼                                               │
│  For Each Session:                                      │
│    • Generate New Token                                 │
│    • Update Database                                    │
│    • Emit WebSocket Event                              │
│         │                                               │
│         ▼                                               │
│  Instructor Receives Update                             │
│         │                                               │
│         ▼                                               │
│  Display New QR Code                                    │
└─────────────────────────────────────────────────────────┘
```

### 6.4.2 Refresh Service Implementation

```javascript
const cron = require('node-cron');

class QRRefreshService {
  constructor(io, sessionModel, qrTokenService) {
    this.io = io;
    this.Session = sessionModel;
    this.qrTokenService = qrTokenService;
    this.interval = null;
  }
  
  start() {
    console.log('Starting QR Refresh Service...');
    
    // Run every 45 seconds
    this.interval = setInterval(async () => {
      await this.refreshAllActiveSessions();
    }, 45000);
  }
  
  stop() {
    if (this.interval) {
      clearInterval(this.interval);
      console.log('QR Refresh Service stopped');
    }
  }
  
  async refreshAllActiveSessions() {
    try {
      // Find all active sessions
      const activeSessions = await this.Session.find({
        status: 'active'
      });
      
      console.log(`Refreshing QR for ${activeSessions.length} active sessions`);
      
      for (const session of activeSessions) {
        await this.refreshSession(session);
      }
    } catch (error) {
      console.error('Error refreshing QR codes:', error);
    }
  }
  
  async refreshSession(session) {
    try {
      // Generate new token
      const newToken = this.qrTokenService.generateToken(
        session._id.toString(),
        session.instructorId.toString()
      );
      
      // Generate QR code image
      const qrCode = await generateQRCode(newToken);
      
      // Update session in database
      await this.Session.updateOne(
        { _id: session._id },
        {
          $set: {
            currentQRToken: newToken,
            qrExpiresAt: new Date(Date.now() + 45000)
          }
        }
      );
      
      // Broadcast to instructor via WebSocket
      this.io.to(`session_${session._id}`).emit('qr_refresh', {
        sessionId: session._id.toString(),
        qrCode: qrCode,
        token: newToken,
        expiresAt: Date.now() + 45000
      });
      
      console.log(`QR refreshed for session ${session._id}`);
    } catch (error) {
      console.error(`Error refreshing session ${session._id}:`, error);
    }
  }
}

module.exports = QRRefreshService;
```

### 6.4.3 Service Initialization

```javascript
// In server.js
const QRRefreshService = require('./services/qrRefreshService');

// Initialize service
const qrRefreshService = new QRRefreshService(
  io,
  Session,
  qrTokenService
);

// Start service
qrRefreshService.start();

// Graceful shutdown
process.on('SIGTERM', () => {
  qrRefreshService.stop();
  process.exit(0);
});
```

---

## 6.5 QR Token Validation

### 6.5.1 Validation Flow

```
Student Scans QR → Extract Token → Backend Receives Token
                                          ↓
                                   Validate JWT Signature
                                          ↓
                                   Check Token Expiration
                                          ↓
                                   Verify Session Exists
                                          ↓
                                   Check Session Active
                                          ↓
                                   Verify Token Currency
                                          ↓
                                   All Valid? → Proceed
```

### 6.5.2 Validation Implementation

```javascript
class QRTokenService {
  constructor(secretKey) {
    this.SECRET_KEY = secretKey;
  }
  
  generateToken(sessionId, instructorId) {
    const now = Date.now();
    
    const payload = {
      sessionId,
      instructorId,
      timestamp: now,
      expiresAt: now + 45000,
      nonce: this.generateNonce()
    };
    
    return jwt.sign(payload, this.SECRET_KEY, {
      algorithm: 'HS256'
    });
  }
  
  async validateToken(token, sessionId) {
    try {
      // Step 1: Verify JWT signature
      const decoded = jwt.verify(token, this.SECRET_KEY);
      
      // Step 2: Check token expiration
      if (Date.now() > decoded.expiresAt) {
        return {
          valid: false,
          reason: 'QR code has expired'
        };
      }
      
      // Step 3: Verify session ID matches
      if (decoded.sessionId !== sessionId) {
        return {
          valid: false,
          reason: 'QR code does not match session'
        };
      }
      
      // Step 4: Get session from database
      const session = await Session.findById(sessionId);
      
      if (!session) {
        return {
          valid: false,
          reason: 'Invalid session'
        };
      }
      
      // Step 5: Check session is active
      if (session.status !== 'active') {
        return {
          valid: false,
          reason: 'Session is not active'
        };
      }
      
      // Step 6: Verify token is current (not old)
      if (session.currentQRToken !== token) {
        return {
          valid: false,
          reason: 'QR code is outdated. Please scan the latest QR code.'
        };
      }
      
      // All validations passed
      return {
        valid: true,
        decoded: decoded
      };
      
    } catch (error) {
      if (error.name === 'JsonWebTokenError') {
        return {
          valid: false,
          reason: 'Invalid QR code signature'
        };
      }
      
      if (error.name === 'TokenExpiredError') {
        return {
          valid: false,
          reason: 'QR code has expired'
        };
      }
      
      return {
        valid: false,
        reason: 'QR code validation failed'
      };
    }
  }
  
  generateNonce() {
    return require('crypto').randomBytes(8).toString('hex');
  }
}

module.exports = QRTokenService;
```

---

## 6.6 Security Mechanisms

### 6.6.1 Preventing Screenshot Attacks

**Problem:** Student takes screenshot of QR code and uses it later

**Solution:**
1. **Timestamp Validation**: Token expires after 45 seconds
2. **Token Currency Check**: Backend verifies token matches `currentQRToken` in session
3. **Auto-Refresh**: New token generated every 45 seconds, old token becomes invalid

**How it works:**
```
Time 0:00 → QR1 generated (valid)
Time 0:30 → Student takes screenshot of QR1
Time 0:45 → QR2 generated, QR1 becomes invalid
Time 1:00 → Student tries to use screenshot
           → Backend checks: token != currentQRToken
           → Rejected: "QR code is outdated"
```

### 6.6.2 Preventing Replay Attacks

**Problem:** Attacker intercepts token and reuses it

**Solution:**
1. **Nonce**: Each token has unique random value
2. **Timestamp**: Token valid only for 45 seconds
3. **One-time Use**: After attendance marked, duplicate check prevents reuse

**Implementation:**
```javascript
// Optional: Track used nonces (for extra security)
const usedNonces = new Set();

function checkNonce(nonce) {
  if (usedNonces.has(nonce)) {
    return false; // Already used
  }
  
  usedNonces.add(nonce);
  
  // Clean up old nonces after 2 minutes
  setTimeout(() => {
    usedNonces.delete(nonce);
  }, 120000);
  
  return true;
}
```

### 6.6.3 Preventing Token Tampering

**Problem:** Attacker modifies token payload

**Solution:**
- **JWT Signature**: Any modification invalidates signature
- **Backend Verification**: Always verify signature before trusting data

**Example:**
```javascript
// Attacker tries to modify sessionId
const originalToken = "eyJhbGci...xyz123";
const tamperedToken = "eyJhbGci...abc456"; // Modified

// Backend verification
jwt.verify(tamperedToken, SECRET_KEY);
// Throws: JsonWebTokenError: invalid signature
```

### 6.6.4 Preventing Session Hijacking

**Problem:** Student uses QR from different session

**Solution:**
- **Session ID Binding**: Token contains sessionId
- **Validation**: Backend verifies sessionId matches

---

## 6.7 API Endpoints

### 6.7.1 Get Current QR Code

```javascript
// GET /api/instructor/session/:sessionId/qr
router.get('/session/:sessionId/qr', authMiddleware, async (req, res) => {
  try {
    const { sessionId } = req.params;
    
    // Verify instructor owns this session
    const session = await Session.findOne({
      _id: sessionId,
      instructorId: req.user.id
    });
    
    if (!session) {
      return res.status(404).json({
        error: 'Session not found'
      });
    }
    
    if (session.status !== 'active') {
      return res.status(400).json({
        error: 'Session is not active'
      });
    }
    
    // Check if current token is expired
    if (Date.now() > session.qrExpiresAt) {
      // Generate new token
      const newToken = qrTokenService.generateToken(
        sessionId,
        req.user.id
      );
      
      const qrCode = await generateQRCode(newToken);
      
      // Update session
      await Session.updateOne(
        { _id: sessionId },
        {
          currentQRToken: newToken,
          qrExpiresAt: new Date(Date.now() + 45000)
        }
      );
      
      return res.json({
        qrCode: qrCode,
        token: newToken,
        expiresAt: Date.now() + 45000
      });
    }
    
    // Return current token
    const qrCode = await generateQRCode(session.currentQRToken);
    
    res.json({
      qrCode: qrCode,
      token: session.currentQRToken,
      expiresAt: session.qrExpiresAt.getTime()
    });
    
  } catch (error) {
    res.status(500).json({
      error: 'Failed to get QR code'
    });
  }
});
```

### 6.7.2 Validate QR Token (Internal)

```javascript
// Used internally by attendance marking endpoint
async function validateQRToken(token, sessionId) {
  const validation = await qrTokenService.validateToken(token, sessionId);
  
  if (!validation.valid) {
    throw new Error(validation.reason);
  }
  
  return validation.decoded;
}
```

---

## 6.8 Frontend QR Scanner

### 6.8.1 Student QR Scanner Component

```javascript
import React, { useState, useEffect } from 'react';
import { Html5QrcodeScanner } from 'html5-qrcode';

function QRScanner({ onScanSuccess, onScanError }) {
  const [scanning, setScanning] = useState(false);
  
  useEffect(() => {
    const scanner = new Html5QrcodeScanner(
      "qr-reader",
      { 
        fps: 10,
        qrbox: 250
      }
    );
    
    scanner.render(onScanSuccessHandler, onScanErrorHandler);
    
    function onScanSuccessHandler(decodedText) {
      // Stop scanning
      scanner.clear();
      setScanning(false);
      
      // Pass token to parent
      onScanSuccess(decodedText);
    }
    
    function onScanErrorHandler(error) {
      // Ignore scan errors (happens continuously while scanning)
    }
    
    setScanning(true);
    
    return () => {
      scanner.clear();
    };
  }, []);
  
  return (
    <div className="qr-scanner">
      <h3>Scan QR Code</h3>
      <div id="qr-reader"></div>
      {scanning && <p>Point camera at QR code...</p>}
    </div>
  );
}

export default QRScanner;
```

### 6.8.2 Usage in Attendance Flow

```javascript
function AttendanceFlow() {
  const [step, setStep] = useState('face'); // 'face' or 'qr'
  const [faceVerified, setFaceVerified] = useState(false);
  const [qrToken, setQrToken] = useState(null);
  
  async function handleFaceVerified() {
    setFaceVerified(true);
    setStep('qr');
  }
  
  async function handleQRScanned(token) {
    setQrToken(token);
    
    // Submit attendance
    try {
      const response = await fetch('/api/student/attendance/mark', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          qrToken: token,
          faceVerified: true
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        alert('Attendance marked successfully!');
      } else {
        alert(`Error: ${data.message}`);
      }
    } catch (error) {
      alert('Failed to mark attendance');
    }
  }
  
  return (
    <div>
      {step === 'face' && (
        <FaceVerification onSuccess={handleFaceVerified} />
      )}
      
      {step === 'qr' && (
        <QRScanner 
          onScanSuccess={handleQRScanned}
          onScanError={(err) => console.error(err)}
        />
      )}
    </div>
  );
}
```

---

## 6.9 Testing QR System

### 6.9.1 Test Cases

**Test 1: Valid QR Code**
- Scan current QR code
- Expected: Attendance marked successfully

**Test 2: Expired QR Code**
- Wait 46 seconds after QR generation
- Scan QR code
- Expected: "QR code has expired"

**Test 3: Old QR Code (After Refresh)**
- Take screenshot of QR at time T
- Wait for refresh (45 seconds)
- Scan screenshot
- Expected: "QR code is outdated"

**Test 4: Stopped Session**
- Instructor stops session
- Student scans QR
- Expected: "Session is not active"

**Test 5: Tampered QR Code**
- Modify QR token manually
- Scan modified QR
- Expected: "Invalid QR code signature"

**Test 6: Wrong Session QR**
- Scan QR from different session
- Expected: "QR code does not match session"

### 6.9.2 Performance Tests

- QR generation time: < 100ms
- QR validation time: < 50ms
- Refresh cycle accuracy: ±1 second
- WebSocket latency: < 500ms

