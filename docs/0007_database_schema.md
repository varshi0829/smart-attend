# Database Schema Design
# MongoDB Collections and Data Models

---

## 7.1 Database Overview

**Database Type:** MongoDB (NoSQL Document Database)

**Database Name:** `attendance_system`

**Collections:**
1. users - User accounts (instructors and students)
2. sessions - Attendance sessions
3. attendance - Attendance records
4. face_data - Face embeddings
5. classes - Class/course information

---

## 7.2 Users Collection

### 7.2.1 Schema

```javascript
{
  _id: ObjectId,
  email: String,
  password: String,        // bcrypt hashed
  role: String,            // "instructor" or "student"
  name: String,
  rollNumber: String,      // for students only
  department: String,
  phone: String,
  profileImage: String,    // URL or base64
  isActive: Boolean,
  createdAt: Date,
  updatedAt: Date
}
```

### 7.2.2 Mongoose Model

```javascript
const mongoose = require('mongoose');

const userSchema = new mongoose.Schema({
  email: {
    type: String,
    required: true,
    unique: true,
    lowercase: true,
    trim: true
  },
  password: {
    type: String,
    required: true
  },
  role: {
    type: String,
    required: true,
    enum: ['instructor', 'student']
  },
  name: {
    type: String,
    required: true
  },
  rollNumber: {
    type: String,
    sparse: true,  // Only for students
    unique: true
  },
  department: {
    type: String,
    default: ''
  },
  phone: {
    type: String,
    default: ''
  },
  profileImage: {
    type: String,
    default: ''
  },
  isActive: {
    type: Boolean,
    default: true
  }
}, {
  timestamps: true
});

// Index for faster queries
userSchema.index({ email: 1 });
userSchema.index({ role: 1 });
userSchema.index({ rollNumber: 1 });

const User = mongoose.model('User', userSchema);

module.exports = User;
```

### 7.2.3 Example Documents

**Instructor:**
```javascript
{
  _id: ObjectId("65f8a1b2c3d4e5f6a7b8c9d1"),
  email: "john.doe@university.edu",
  password: "$2b$10$abcdefghijklmnopqrstuvwxyz123456",
  role: "instructor",
  name: "Dr. John Doe",
  department: "Computer Science",
  phone: "+1234567890",
  profileImage: "",
  isActive: true,
  createdAt: ISODate("2026-03-01T10:00:00Z"),
  updatedAt: ISODate("2026-03-01T10:00:00Z")
}
```

**Student:**
```javascript
{
  _id: ObjectId("65f8a1b2c3d4e5f6a7b8c9d2"),
  email: "alice.smith@student.edu",
  password: "$2b$10$zyxwvutsrqponmlkjihgfedcba654321",
  role: "student",
  name: "Alice Smith",
  rollNumber: "CS2026001",
  department: "Computer Science",
  phone: "+1234567891",
  profileImage: "",
  isActive: true,
  createdAt: ISODate("2026-03-01T11:00:00Z"),
  updatedAt: ISODate("2026-03-01T11:00:00Z")
}
```

---

## 7.3 Sessions Collection

### 7.3.1 Schema

```javascript
{
  _id: ObjectId,
  instructorId: ObjectId,
  classId: ObjectId,
  className: String,
  subject: String,
  status: String,          // "active" or "stopped"
  startTime: Date,
  stopTime: Date,
  currentQRToken: String,  // Current valid JWT token
  qrExpiresAt: Date,
  totalStudents: Number,   // Expected students
  presentCount: Number,    // Students marked present
  createdAt: Date,
  updatedAt: Date
}
```

### 7.3.2 Mongoose Model

```javascript
const sessionSchema = new mongoose.Schema({
  instructorId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  classId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'Class',
    required: true
  },
  className: {
    type: String,
    required: true
  },
  subject: {
    type: String,
    default: ''
  },
  status: {
    type: String,
    required: true,
    enum: ['active', 'stopped'],
    default: 'active'
  },
  startTime: {
    type: Date,
    required: true
  },
  stopTime: {
    type: Date,
    default: null
  },
  currentQRToken: {
    type: String,
    default: null
  },
  qrExpiresAt: {
    type: Date,
    default: null
  },
  totalStudents: {
    type: Number,
    default: 0
  },
  presentCount: {
    type: Number,
    default: 0
  }
}, {
  timestamps: true
});

// Indexes
sessionSchema.index({ instructorId: 1, createdAt: -1 });
sessionSchema.index({ status: 1 });
sessionSchema.index({ classId: 1, createdAt: -1 });

const Session = mongoose.model('Session', sessionSchema);

module.exports = Session;
```

### 7.3.3 Example Document

```javascript
{
  _id: ObjectId("65f8a1b2c3d4e5f6a7b8c9d3"),
  instructorId: ObjectId("65f8a1b2c3d4e5f6a7b8c9d1"),
  classId: ObjectId("65f8a1b2c3d4e5f6a7b8c9d4"),
  className: "Computer Science 101",
  subject: "Data Structures",
  status: "active",
  startTime: ISODate("2026-03-07T11:00:00Z"),
  stopTime: null,
  currentQRToken: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  qrExpiresAt: ISODate("2026-03-07T11:00:45Z"),
  totalStudents: 50,
  presentCount: 23,
  createdAt: ISODate("2026-03-07T11:00:00Z"),
  updatedAt: ISODate("2026-03-07T11:05:30Z")
}
```

---

## 7.4 Attendance Collection

### 7.4.1 Schema

```javascript
{
  _id: ObjectId,
  sessionId: ObjectId,
  studentId: ObjectId,
  markedAt: Date,
  faceVerified: Boolean,
  qrVerified: Boolean,
  confidence: Number,      // Face verification confidence
  ipAddress: String,
  userAgent: String,
  createdAt: Date
}
```

### 7.4.2 Mongoose Model

```javascript
const attendanceSchema = new mongoose.Schema({
  sessionId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'Session',
    required: true
  },
  studentId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  markedAt: {
    type: Date,
    required: true,
    default: Date.now
  },
  faceVerified: {
    type: Boolean,
    required: true
  },
  qrVerified: {
    type: Boolean,
    required: true
  },
  confidence: {
    type: Number,
    default: 0
  },
  ipAddress: {
    type: String,
    default: ''
  },
  userAgent: {
    type: String,
    default: ''
  }
}, {
  timestamps: true
});

// Compound index to prevent duplicate attendance
attendanceSchema.index({ sessionId: 1, studentId: 1 }, { unique: true });

// Indexes for queries
attendanceSchema.index({ studentId: 1, createdAt: -1 });
attendanceSchema.index({ sessionId: 1, markedAt: 1 });

const Attendance = mongoose.model('Attendance', attendanceSchema);

module.exports = Attendance;
```

### 7.4.3 Example Document

```javascript
{
  _id: ObjectId("65f8a1b2c3d4e5f6a7b8c9d5"),
  sessionId: ObjectId("65f8a1b2c3d4e5f6a7b8c9d3"),
  studentId: ObjectId("65f8a1b2c3d4e5f6a7b8c9d2"),
  markedAt: ISODate("2026-03-07T11:05:30Z"),
  faceVerified: true,
  qrVerified: true,
  confidence: 0.87,
  ipAddress: "192.168.1.100",
  userAgent: "Mozilla/5.0...",
  createdAt: ISODate("2026-03-07T11:05:30Z")
}
```

---

## 7.5 Face Data Collection

### 7.5.1 Schema

```javascript
{
  _id: ObjectId,
  studentId: ObjectId,
  embeddings: [[Number]],  // Array of embedding arrays
  imageCount: Number,
  lastUpdated: Date,
  createdAt: Date,
  updatedAt: Date
}
```

### 7.5.2 Mongoose Model

```javascript
const faceDataSchema = new mongoose.Schema({
  studentId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true,
    unique: true
  },
  embeddings: {
    type: [[Number]],  // Array of arrays
    required: true
  },
  imageCount: {
    type: Number,
    required: true
  },
  lastUpdated: {
    type: Date,
    default: Date.now
  }
}, {
  timestamps: true
});

// Index
faceDataSchema.index({ studentId: 1 });

const FaceData = mongoose.model('FaceData', faceDataSchema);

module.exports = FaceData;
```

### 7.5.3 Example Document

```javascript
{
  _id: ObjectId("65f8a1b2c3d4e5f6a7b8c9d6"),
  studentId: ObjectId("65f8a1b2c3d4e5f6a7b8c9d2"),
  embeddings: [
    [0.123, -0.456, 0.789, ..., 0.234],  // 512 values
    [0.145, -0.423, 0.801, ..., 0.256],  // 512 values
    [0.134, -0.441, 0.795, ..., 0.245]   // 512 values
  ],
  imageCount: 3,
  lastUpdated: ISODate("2026-03-07T10:00:00Z"),
  createdAt: ISODate("2026-03-07T10:00:00Z"),
  updatedAt: ISODate("2026-03-07T10:00:00Z")
}
```

---

## 7.6 Classes Collection

### 7.6.1 Schema

```javascript
{
  _id: ObjectId,
  className: String,
  courseCode: String,
  department: String,
  semester: String,
  instructorId: ObjectId,
  students: [ObjectId],    // Array of student IDs
  schedule: [{
    day: String,
    startTime: String,
    endTime: String,
    room: String
  }],
  isActive: Boolean,
  createdAt: Date,
  updatedAt: Date
}
```

### 7.6.2 Mongoose Model

```javascript
const classSchema = new mongoose.Schema({
  className: {
    type: String,
    required: true
  },
  courseCode: {
    type: String,
    required: true,
    unique: true
  },
  department: {
    type: String,
    required: true
  },
  semester: {
    type: String,
    default: ''
  },
  instructorId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  students: [{
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User'
  }],
  schedule: [{
    day: {
      type: String,
      enum: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    },
    startTime: String,
    endTime: String,
    room: String
  }],
  isActive: {
    type: Boolean,
    default: true
  }
}, {
  timestamps: true
});

// Indexes
classSchema.index({ instructorId: 1 });
classSchema.index({ courseCode: 1 });

const Class = mongoose.model('Class', classSchema);

module.exports = Class;
```

### 7.6.3 Example Document

```javascript
{
  _id: ObjectId("65f8a1b2c3d4e5f6a7b8c9d4"),
  className: "Data Structures and Algorithms",
  courseCode: "CS201",
  department: "Computer Science",
  semester: "Spring 2026",
  instructorId: ObjectId("65f8a1b2c3d4e5f6a7b8c9d1"),
  students: [
    ObjectId("65f8a1b2c3d4e5f6a7b8c9d2"),
    ObjectId("65f8a1b2c3d4e5f6a7b8c9d7"),
    ObjectId("65f8a1b2c3d4e5f6a7b8c9d8")
  ],
  schedule: [
    {
      day: "Monday",
      startTime: "10:00",
      endTime: "11:30",
      room: "Room 301"
    },
    {
      day: "Wednesday",
      startTime: "10:00",
      endTime: "11:30",
      room: "Room 301"
    }
  ],
  isActive: true,
  createdAt: ISODate("2026-03-01T10:00:00Z"),
  updatedAt: ISODate("2026-03-01T10:00:00Z")
}
```

---

## 7.7 Database Relationships

```
┌─────────────┐
│    Users    │
│  (role:     │
│  instructor)│
└──────┬──────┘
       │
       │ instructorId
       │
       ▼
┌─────────────┐         ┌──────────────┐
│   Classes   │◄────────│   Sessions   │
└──────┬──────┘ classId └──────┬───────┘
       │                       │
       │ students[]            │ sessionId
       │                       │
       ▼                       ▼
┌─────────────┐         ┌──────────────┐
│    Users    │◄────────│  Attendance  │
│  (role:     │studentId└──────────────┘
│   student)  │
└──────┬──────┘
       │
       │ studentId
       │
       ▼
┌─────────────┐
│  Face Data  │
└─────────────┘
```

---

## 7.8 Database Queries

### 7.8.1 Common Queries

**Get Active Sessions:**
```javascript
const activeSessions = await Session.find({ status: 'active' });
```

**Get Session with Attendance:**
```javascript
const session = await Session.findById(sessionId)
  .populate('instructorId', 'name email')
  .populate('classId', 'className courseCode');

const attendance = await Attendance.find({ sessionId })
  .populate('studentId', 'name rollNumber')
  .sort({ markedAt: 1 });
```

**Get Student Attendance History:**
```javascript
const history = await Attendance.find({ studentId })
  .populate('sessionId', 'className subject startTime')
  .sort({ createdAt: -1 })
  .limit(50);
```

**Check Duplicate Attendance:**
```javascript
const existing = await Attendance.findOne({
  sessionId: sessionId,
  studentId: studentId
});
```

**Get Class Students:**
```javascript
const classData = await Class.findById(classId)
  .populate('students', 'name rollNumber email');
```

**Get Face Data:**
```javascript
const faceData = await FaceData.findOne({ studentId });
```

### 7.8.2 Aggregation Queries

**Attendance Statistics:**
```javascript
const stats = await Attendance.aggregate([
  {
    $match: { sessionId: mongoose.Types.ObjectId(sessionId) }
  },
  {
    $group: {
      _id: null,
      totalPresent: { $sum: 1 },
      avgConfidence: { $avg: '$confidence' }
    }
  }
]);
```

**Student Attendance Percentage:**
```javascript
const percentage = await Attendance.aggregate([
  {
    $match: { studentId: mongoose.Types.ObjectId(studentId) }
  },
  {
    $lookup: {
      from: 'sessions',
      localField: 'sessionId',
      foreignField: '_id',
      as: 'session'
    }
  },
  {
    $unwind: '$session'
  },
  {
    $group: {
      _id: '$session.classId',
      attended: { $sum: 1 }
    }
  }
]);
```

---

## 7.9 Database Indexes

### 7.9.1 Index Strategy

**Users Collection:**
```javascript
db.users.createIndex({ email: 1 }, { unique: true });
db.users.createIndex({ role: 1 });
db.users.createIndex({ rollNumber: 1 }, { sparse: true, unique: true });
```

**Sessions Collection:**
```javascript
db.sessions.createIndex({ instructorId: 1, createdAt: -1 });
db.sessions.createIndex({ status: 1 });
db.sessions.createIndex({ classId: 1, createdAt: -1 });
```

**Attendance Collection:**
```javascript
db.attendance.createIndex({ sessionId: 1, studentId: 1 }, { unique: true });
db.attendance.createIndex({ studentId: 1, createdAt: -1 });
db.attendance.createIndex({ sessionId: 1, markedAt: 1 });
```

**Face Data Collection:**
```javascript
db.face_data.createIndex({ studentId: 1 }, { unique: true });
```

**Classes Collection:**
```javascript
db.classes.createIndex({ instructorId: 1 });
db.classes.createIndex({ courseCode: 1 }, { unique: true });
```

---

## 7.10 Data Validation

### 7.10.1 Validation Rules

**Email Validation:**
```javascript
email: {
  type: String,
  required: true,
  unique: true,
  validate: {
    validator: function(v) {
      return /^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$/.test(v);
    },
    message: 'Invalid email format'
  }
}
```

**Role Validation:**
```javascript
role: {
  type: String,
  required: true,
  enum: {
    values: ['instructor', 'student'],
    message: 'Role must be either instructor or student'
  }
}
```

**Status Validation:**
```javascript
status: {
  type: String,
  required: true,
  enum: {
    values: ['active', 'stopped'],
    message: 'Status must be either active or stopped'
  }
}
```

---

## 7.11 Database Backup Strategy

**Backup Frequency:**
- Full backup: Daily at 2:00 AM
- Incremental backup: Every 6 hours
- Retention: 30 days

**Backup Command:**
```bash
mongodump --uri="mongodb://localhost:27017/attendance_system" --out=/backup/$(date +%Y%m%d)
```

**Restore Command:**
```bash
mongorestore --uri="mongodb://localhost:27017/attendance_system" /backup/20260307
```

