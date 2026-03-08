# Security Design
# Security Architecture and Threat Mitigation

---

## 9.1 Security Overview

The attendance system implements **defense-in-depth** security with multiple layers:

1. **Authentication Layer** - JWT-based user authentication
2. **Authorization Layer** - Role-based access control
3. **Transport Layer** - HTTPS/TLS encryption
4. **Application Layer** - Input validation and sanitization
5. **Data Layer** - Encrypted storage and secure queries
6. **Verification Layer** - Dual-factor attendance verification

---

## 9.2 Authentication Security

### 9.2.1 Password Security

**Hashing Algorithm:** bcrypt with salt rounds = 10

**Implementation:**
```javascript
const bcrypt = require('bcryptjs');

// Hash password during registration
async function hashPassword(password) {
  const salt = await bcrypt.genSalt(10);
  const hash = await bcrypt.hash(password, salt);
  return hash;
}

// Verify password during login
async function verifyPassword(plainPassword, hashedPassword) {
  return await bcrypt.compare(plainPassword, hashedPassword);
}
```

**Password Requirements:**
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character

**Validation:**
```javascript
function validatePassword(password) {
  const regex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/;
  return regex.test(password);
}
```

### 9.2.2 JWT Token Security

**Token Structure:**
```javascript
{
  header: {
    alg: "HS256",
    typ: "JWT"
  },
  payload: {
    userId: "65f8a1b2c3d4e5f6a7b8c9d2",
    role: "student",
    iat: 1709809200,
    exp: 1709895600  // 24 hours
  },
  signature: "..."
}
```

**Token Generation:**
```javascript
const jwt = require('jsonwebtoken');

function generateAuthToken(userId, role) {
  const payload = {
    userId: userId,
    role: role,
    iat: Math.floor(Date.now() / 1000)
  };
  
  const token = jwt.sign(payload, process.env.JWT_SECRET, {
    expiresIn: '24h',
    algorithm: 'HS256'
  });
  
  return token;
}
```

**Token Verification Middleware:**
```javascript
function authMiddleware(req, res, next) {
  try {
    // Extract token from header
    const authHeader = req.headers.authorization;
    
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(401).json({
        error: 'No token provided'
      });
    }
    
    const token = authHeader.substring(7);
    
    // Verify token
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    
    // Attach user info to request
    req.user = {
      id: decoded.userId,
      role: decoded.role
    };
    
    next();
  } catch (error) {
    if (error.name === 'TokenExpiredError') {
      return res.status(401).json({
        error: 'Token expired'
      });
    }
    
    return res.status(401).json({
      error: 'Invalid token'
    });
  }
}
```

**Secret Key Management:**
- Store in environment variables
- Use strong random key (256-bit minimum)
- Rotate keys periodically
- Never commit to version control

```bash
# Generate strong secret
node -e "console.log(require('crypto').randomBytes(64).toString('hex'))"
```

---

## 9.3 Authorization Security

### 9.3.1 Role-Based Access Control (RBAC)

**Roles:**
- `instructor` - Can manage sessions and view attendance
- `student` - Can mark attendance and view own history

**Authorization Middleware:**
```javascript
function requireRole(...allowedRoles) {
  return (req, res, next) => {
    if (!req.user) {
      return res.status(401).json({
        error: 'Authentication required'
      });
    }
    
    if (!allowedRoles.includes(req.user.role)) {
      return res.status(403).json({
        error: 'Insufficient permissions'
      });
    }
    
    next();
  };
}

// Usage
router.post('/session/start', 
  authMiddleware, 
  requireRole('instructor'), 
  startSession
);
```

### 9.3.2 Resource Ownership Verification

**Verify Instructor Owns Session:**
```javascript
async function verifySessionOwnership(req, res, next) {
  const session = await Session.findById(req.params.sessionId);
  
  if (!session) {
    return res.status(404).json({
      error: 'Session not found'
    });
  }
  
  if (session.instructorId.toString() !== req.user.id) {
    return res.status(403).json({
      error: 'You do not have access to this session'
    });
  }
  
  req.session = session;
  next();
}
```

---

## 9.4 QR Code Security

### 9.4.1 Preventing Screenshot Attacks

**Mechanism:**
1. **Timestamp Validation** - Token expires after 45 seconds
2. **Token Currency Check** - Verify token matches current session token
3. **Auto-Refresh** - New token every 45 seconds invalidates old ones

**Implementation:**
```javascript
async function validateQRToken(token, sessionId) {
  // Verify JWT signature
  const decoded = jwt.verify(token, process.env.JWT_SECRET);
  
  // Check expiration
  if (Date.now() > decoded.expiresAt) {
    throw new Error('QR code has expired');
  }
  
  // Get session
  const session = await Session.findById(sessionId);
  
  // Verify token is current
  if (session.currentQRToken !== token) {
    throw new Error('QR code is outdated');
  }
  
  return decoded;
}
```

**Attack Scenario:**
```
Time 0:00 → Student takes screenshot of QR1
Time 0:45 → System generates QR2, QR1 invalidated
Time 1:00 → Student tries screenshot
           → Backend: token != currentQRToken
           → REJECTED
```

### 9.4.2 Preventing Replay Attacks

**Mechanism:**
1. **Unique Nonce** - Each token has random unique value
2. **Timestamp** - Token valid only for 45 seconds
3. **One-Time Use** - Duplicate attendance check

**Nonce Generation:**
```javascript
function generateNonce() {
  return crypto.randomBytes(16).toString('hex');
}
```

**Optional Nonce Tracking:**
```javascript
const usedNonces = new Map();

function checkNonce(nonce) {
  if (usedNonces.has(nonce)) {
    return false; // Already used
  }
  
  usedNonces.set(nonce, Date.now());
  
  // Clean up old nonces after 2 minutes
  setTimeout(() => {
    usedNonces.delete(nonce);
  }, 120000);
  
  return true;
}
```

### 9.4.3 Preventing Token Tampering

**JWT Signature Verification:**
```javascript
try {
  const decoded = jwt.verify(token, SECRET_KEY);
  // Token is valid and untampered
} catch (error) {
  // Token signature invalid - tampered
  throw new Error('Invalid QR code');
}
```

**Attack Prevention:**
- Any modification to payload invalidates signature
- Backend always verifies signature before trusting data
- Use strong secret key (256-bit)

---

## 9.5 Face Recognition Security

### 9.5.1 Embedding Storage Security

**Encryption (Optional):**
```javascript
const crypto = require('crypto');

function encryptEmbedding(embedding) {
  const algorithm = 'aes-256-gcm';
  const key = Buffer.from(process.env.ENCRYPTION_KEY, 'hex');
  const iv = crypto.randomBytes(16);
  
  const cipher = crypto.createCipheriv(algorithm, key, iv);
  
  const embeddingStr = JSON.stringify(embedding);
  let encrypted = cipher.update(embeddingStr, 'utf8', 'hex');
  encrypted += cipher.final('hex');
  
  const authTag = cipher.getAuthTag();
  
  return {
    encrypted: encrypted,
    iv: iv.toString('hex'),
    authTag: authTag.toString('hex')
  };
}

function decryptEmbedding(encryptedData) {
  const algorithm = 'aes-256-gcm';
  const key = Buffer.from(process.env.ENCRYPTION_KEY, 'hex');
  const iv = Buffer.from(encryptedData.iv, 'hex');
  const authTag = Buffer.from(encryptedData.authTag, 'hex');
  
  const decipher = crypto.createDecipheriv(algorithm, key, iv);
  decipher.setAuthTag(authTag);
  
  let decrypted = decipher.update(encryptedData.encrypted, 'hex', 'utf8');
  decrypted += decipher.final('utf8');
  
  return JSON.parse(decrypted);
}
```

### 9.5.2 Anti-Spoofing (Future Enhancement)

**Liveness Detection:**
- Blink detection
- Head movement detection
- Texture analysis
- Challenge-response (smile, turn head)

**Basic Blink Detection:**
```python
def detect_blink(frames):
    """
    Detect blink in video frames
    Returns True if blink detected
    """
    eye_aspect_ratios = []
    
    for frame in frames:
        landmarks = detect_landmarks(frame)
        ear = calculate_eye_aspect_ratio(landmarks)
        eye_aspect_ratios.append(ear)
    
    # Check if EAR drops and rises (blink pattern)
    threshold = 0.2
    blink_detected = False
    
    for i in range(1, len(eye_aspect_ratios) - 1):
        if (eye_aspect_ratios[i] < threshold and 
            eye_aspect_ratios[i-1] > threshold and 
            eye_aspect_ratios[i+1] > threshold):
            blink_detected = True
            break
    
    return blink_detected
```

---

## 9.6 Input Validation

### 9.6.1 Request Validation

**Email Validation:**
```javascript
function validateEmail(email) {
  const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return regex.test(email);
}
```

**Sanitization:**
```javascript
const validator = require('validator');

function sanitizeInput(input) {
  // Trim whitespace
  let sanitized = input.trim();
  
  // Escape HTML
  sanitized = validator.escape(sanitized);
  
  return sanitized;
}
```

**Request Validation Middleware:**
```javascript
const { body, validationResult } = require('express-validator');

const validateRegistration = [
  body('email').isEmail().normalizeEmail(),
  body('password').isLength({ min: 8 }),
  body('name').trim().notEmpty(),
  body('role').isIn(['instructor', 'student']),
  
  (req, res, next) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({
        errors: errors.array()
      });
    }
    next();
  }
];

router.post('/register', validateRegistration, registerUser);
```

### 9.6.2 SQL/NoSQL Injection Prevention

**MongoDB Injection Prevention:**
```javascript
// BAD - Vulnerable
const user = await User.findOne({
  email: req.body.email  // Could be object injection
});

// GOOD - Safe
const user = await User.findOne({
  email: String(req.body.email)
});

// BETTER - Use Mongoose schema validation
// Mongoose automatically sanitizes
```

**Query Sanitization:**
```javascript
function sanitizeQuery(query) {
  // Remove $ operators from user input
  const sanitized = {};
  
  for (const key in query) {
    if (!key.startsWith('$')) {
      sanitized[key] = query[key];
    }
  }
  
  return sanitized;
}
```

---

## 9.7 Rate Limiting

### 9.7.1 Implementation

```javascript
const rateLimit = require('express-rate-limit');

// General rate limiter
const generalLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 60, // 60 requests per minute
  message: 'Too many requests, please try again later'
});

// Strict limiter for authentication
const authLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 5, // 5 attempts per minute
  message: 'Too many login attempts, please try again later'
});

// Face verification limiter
const faceLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 10,
  message: 'Too many face verification attempts'
});

// Apply to routes
app.use('/api/', generalLimiter);
app.use('/api/auth/login', authLimiter);
app.use('/api/student/face/verify', faceLimiter);
```

### 9.7.2 Distributed Rate Limiting

**Using Redis:**
```javascript
const RedisStore = require('rate-limit-redis');
const redis = require('redis');

const client = redis.createClient();

const limiter = rateLimit({
  store: new RedisStore({
    client: client,
    prefix: 'rl:'
  }),
  windowMs: 60 * 1000,
  max: 60
});
```

---

## 9.8 CORS Configuration

```javascript
const cors = require('cors');

const corsOptions = {
  origin: function (origin, callback) {
    const allowedOrigins = [
      'https://instructor.attendance-system.com',
      'https://student.attendance-system.com'
    ];
    
    if (!origin || allowedOrigins.indexOf(origin) !== -1) {
      callback(null, true);
    } else {
      callback(new Error('Not allowed by CORS'));
    }
  },
  credentials: true,
  optionsSuccessStatus: 200
};

app.use(cors(corsOptions));
```

---

## 9.9 HTTPS/TLS

### 9.9.1 SSL Certificate

**Production:**
- Use Let's Encrypt for free SSL certificates
- Auto-renewal with certbot

**Configuration:**
```javascript
const https = require('https');
const fs = require('fs');

const options = {
  key: fs.readFileSync('/path/to/private-key.pem'),
  cert: fs.readFileSync('/path/to/certificate.pem')
};

https.createServer(options, app).listen(443);
```

### 9.9.2 Security Headers

```javascript
const helmet = require('helmet');

app.use(helmet());

// Custom headers
app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-XSS-Protection', '1; mode=block');
  res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  next();
});
```

---

## 9.10 Logging and Monitoring

### 9.10.1 Security Event Logging

```javascript
const winston = require('winston');

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.json(),
  transports: [
    new winston.transports.File({ filename: 'error.log', level: 'error' }),
    new winston.transports.File({ filename: 'security.log', level: 'warn' }),
    new winston.transports.File({ filename: 'combined.log' })
  ]
});

// Log security events
function logSecurityEvent(event, details) {
  logger.warn('Security Event', {
    event: event,
    details: details,
    timestamp: new Date().toISOString()
  });
}

// Usage
logSecurityEvent('INVALID_TOKEN', {
  userId: req.user?.id,
  ip: req.ip,
  userAgent: req.headers['user-agent']
});
```

### 9.10.2 Monitored Events

- Failed login attempts
- Invalid token usage
- Expired QR code attempts
- Duplicate attendance attempts
- Face verification failures
- Rate limit violations
- Unauthorized access attempts

---

## 9.11 Data Privacy

### 9.11.1 GDPR Compliance

**Data Minimization:**
- Collect only necessary data
- Store face embeddings, not raw images
- Delete old session data after retention period

**Right to Erasure:**
```javascript
async function deleteUserData(userId) {
  // Delete user account
  await User.deleteOne({ _id: userId });
  
  // Delete face data
  await FaceData.deleteOne({ studentId: userId });
  
  // Anonymize attendance records (keep for statistics)
  await Attendance.updateMany(
    { studentId: userId },
    { $set: { studentId: null, anonymized: true } }
  );
}
```

### 9.11.2 Data Retention

**Policy:**
- Active session data: Retained indefinitely
- Stopped session data: 2 years
- Face embeddings: Until user deletion
- Logs: 90 days

**Cleanup Job:**
```javascript
async function cleanupOldData() {
  const twoYearsAgo = new Date();
  twoYearsAgo.setFullYear(twoYearsAgo.getFullYear() - 2);
  
  // Delete old stopped sessions
  await Session.deleteMany({
    status: 'stopped',
    stopTime: { $lt: twoYearsAgo }
  });
  
  // Delete associated attendance records
  await Attendance.deleteMany({
    createdAt: { $lt: twoYearsAgo }
  });
}

// Run daily
cron.schedule('0 2 * * *', cleanupOldData);
```

---

## 9.12 Security Checklist

**Authentication:**
- ✓ Passwords hashed with bcrypt
- ✓ JWT tokens with expiration
- ✓ Secure secret key management
- ✓ Token verification on all protected routes

**Authorization:**
- ✓ Role-based access control
- ✓ Resource ownership verification
- ✓ Principle of least privilege

**QR Security:**
- ✓ Signed JWT tokens
- ✓ Timestamp validation
- ✓ Token currency check
- ✓ Auto-refresh mechanism
- ✓ Nonce for replay prevention

**Face Recognition:**
- ✓ Secure embedding storage
- ✓ Threshold-based verification
- ✓ Confidence score logging

**Network Security:**
- ✓ HTTPS/TLS encryption
- ✓ CORS configuration
- ✓ Security headers
- ✓ Rate limiting

**Input Validation:**
- ✓ Request validation
- ✓ Input sanitization
- ✓ Injection prevention

**Monitoring:**
- ✓ Security event logging
- ✓ Failed attempt tracking
- ✓ Anomaly detection

**Data Privacy:**
- ✓ Data minimization
- ✓ Encryption at rest (optional)
- ✓ Data retention policy
- ✓ User data deletion

