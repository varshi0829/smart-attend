# Role-Based Access Control (RBAC) System Design

## 1. Overview
The Smart Attendance system currently relies on basic user models (`instructor` and `student`). To scale for institutional use, we must implement a hierarchical Role-Based Access Control (RBAC) system. 

This document defines the architecture, data flow, and frontend/backend enforcement strategies for the new RBAC system covering: Principal, HOD, Faculty, and Class Teacher.

---

## 2. Role Definitions & Hierarchy

### Level 1: Principal (Global Admin)
- **Scope:** Global.
- **Capabilities:** High-level dashboard view, access to all departments, all faculty, and all class sessions across the institution.

### Level 2: HOD (Department Admin)
- **Scope:** Department-specific.
- **Capabilities:** Department-level dashboard, access to all faculty and class sessions strictly within their assigned `department`.

### Level 3: Faculty (Standard Instructor)
- **Scope:** Self-specific.
- **Capabilities:** Standard instructor dashboard. Can only view and manage sessions where `instructorId` matches their own User ID.

### Overlay Level: Class Teacher
- **Scope:** Class-specific.
- **Capabilities:** A Class Teacher is essentially a Faculty member with augmented read privileges. They can view all sessions and reports belonging to their specifically assigned `year`, `department`, and `section`, regardless of which faculty member taught the session.

---

## 3. Database Architecture Changes

To support these roles, we must upgrade the `User` schema. 

### Proposed Model Changes (`models/User.js`)
```javascript
const userSchema = new mongoose.Schema({
  // Existing fields...
  email: { type: String, required: true },
  name: { type: String, required: true },
  
  // Updated Role Field
  role: {
    type: String,
    required: true,
    enum: ['student', 'faculty', 'hod', 'principal'],
    default: 'student'
  },
  
  // Scope Claims
  department: { 
    type: String, 
    required: function() { return ['faculty', 'hod'].includes(this.role); }
  },
  
  // Class Teacher Claim (Optional for faculty)
  assignedClass: {
    isClassTeacher: { type: Boolean, default: false },
    year: { type: String },
    section: { type: String }
  }
});
```

*(Note: Class teacher is modeled as a claim on top of the 'faculty' role, rather than a standalone role, to preserve semantic hierarchy).*

---

## 4. Backend Access Control Design

### Middleware (`middleware/requireRole.js`)
A JWT middleware will inject `req.user`. We will implement a role-gatekeeper:

```javascript
const requireRole = (allowedRoles) => {
  return (req, res, next) => {
    if (!req.user || !allowedRoles.includes(req.user.role)) {
      return res.status(403).json({ error: "Access Denied: Insufficient Privileges" });
    }
    next();
  }
}
```

### Data Filtering Logic (API Controllers)
When fetching sessions (`GET /api/attendance/reports/list`), the backend will dynamically generate the MongoDB filter object based on the requester's role footprint:

```javascript
let filter = {};

switch (req.user.role) {
  case 'principal':
    // Global access: no filters applied
    break;
    
  case 'hod':
    // Department access
    filter.department = req.user.department;
    break;
    
  case 'faculty':
    if (req.user.assignedClass && req.user.assignedClass.isClassTeacher) {
      // Class Teacher: Self sessions OR any session for their assigned class
      filter.$or = [
        { instructorId: req.user.id },
        { 
          department: req.user.department, 
          year: req.user.assignedClass.year, 
          section: req.user.assignedClass.section 
        }
      ];
    } else {
      // Standard Faculty: Only self sessions
      filter.instructorId = req.user.id;
    }
    break;
}

const reports = await Session.find(filter).sort({ createdAt: -1 });
```

---

## 5. Frontend Dashboard Adaptation

The `Instructor Portal` will consume the JWT `user` object and restructure the UI dynamically.

1. **JWT Decode:** On login, `localStorage` will capture the user's role and scope claims.
2. **Conditional Rendering:**
   - `<div id="principalDashboard">` rendered if `role === 'principal'`.
   - `<div id="hodDashboard">` rendered if `role === 'hod'`.
   - Standard `/reports` views will append the necessary filters to the API automatically by merit of the backend handling the scope.
3. **Class Teacher View:** A "My Assigned Class" dedicated tab will render if `user.assignedClass.isClassTeacher === true`.
