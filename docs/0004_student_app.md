# Student Web Application Design
# Complete UI/UX and Authentication Flow

---

## 4.1 Application Overview

**Purpose:** Web application for students to mark attendance via face + QR verification

**Technology Stack:**
- React.js 18+ or Vue.js 3+
- React Router / Vue Router
- Axios for API calls
- html5-qrcode for QR scanning
- Webcam library for camera access
- TailwindCSS / Material-UI for styling

---

## 4.2 Authentication System

### 4.2.1 Login Flow

```
Landing Page → Login Form → Validate → Get JWT → Store Token → Home
```

**Login Component:**
```javascript
import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

function StudentLogin() {
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await axios.post('/api/auth/login', {
        email: formData.email,
        password: formData.password,
        role: 'student'
      });

      // Store token and user data
      localStorage.setItem('token', response.data.token);
      localStorage.setItem('user', JSON.stringify(response.data.user));

      // Redirect to home
      navigate('/home');
    } catch (err) {
      setError(err.response?.data?.error || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>Student Login</h1>
          <p>Smart Attendance System</p>
        </div>

        {error && (
          <div className="error-alert">
            <span className="error-icon">⚠</span>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="email">Email Address</label>
            <input
              id="email"
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({...formData, email: e.target.value})}
              required
              placeholder="student@university.edu"
              autoComplete="email"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({...formData, password: e.target.value})}
              required
              placeholder="Enter your password"
              autoComplete="current-password"
            />
          </div>

          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? (
              <>
                <span className="spinner"></span>
                Logging in...
              </>
            ) : (
              'Login'
            )}
          </button>
        </form>

        <div className="login-footer">
          <a href="/forgot-password">Forgot Password?</a>
          <span className="separator">•</span>
          <a href="/register">Create Account</a>
        </div>
      </div>
    </div>
  );
}

export default StudentLogin;
```

### 4.2.2 Registration Component

```javascript
import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

function StudentRegister() {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    name: '',
    rollNumber: '',
    department: '',
    phone: ''
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const validateForm = () => {
    const newErrors = {};

    if (formData.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    }

    if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }

    if (!formData.rollNumber) {
      newErrors.rollNumber = 'Roll number is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setLoading(true);

    try {
      await axios.post('/api/auth/register', {
        email: formData.email,
        password: formData.password,
        role: 'student',
        name: formData.name,
        rollNumber: formData.rollNumber,
        department: formData.department,
        phone: formData.phone
      });

      alert('Registration successful! Please login.');
      navigate('/login');
    } catch (err) {
      setErrors({ 
        submit: err.response?.data?.error || 'Registration failed' 
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="register-container">
      <div className="register-card">
        <h1>Create Student Account</h1>

        {errors.submit && (
          <div className="error-alert">{errors.submit}</div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-group">
              <label>Full Name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
                required
              />
            </div>

            <div className="form-group">
              <label>Roll Number *</label>
              <input
                type="text"
                value={formData.rollNumber}
                onChange={(e) => setFormData({...formData, rollNumber: e.target.value})}
                required
              />
              {errors.rollNumber && <span className="error-text">{errors.rollNumber}</span>}
            </div>
          </div>

          <div className="form-group">
            <label>Email *</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({...formData, email: e.target.value})}
              required
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Department</label>
              <input
                type="text"
                value={formData.department}
                onChange={(e) => setFormData({...formData, department: e.target.value})}
              />
            </div>

            <div className="form-group">
              <label>Phone</label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) => setFormData({...formData, phone: e.target.value})}
              />
            </div>
          </div>

          <div className="form-group">
            <label>Password *</label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({...formData, password: e.target.value})}
              required
            />
            {errors.password && <span className="error-text">{errors.password}</span>}
          </div>

          <div className="form-group">
            <label>Confirm Password *</label>
            <input
              type="password"
              value={formData.confirmPassword}
              onChange={(e) => setFormData({...formData, confirmPassword: e.target.value})}
              required
            />
            {errors.confirmPassword && <span className="error-text">{errors.confirmPassword}</span>}
          </div>

          <button type="submit" disabled={loading}>
            {loading ? 'Creating Account...' : 'Register'}
          </button>
        </form>

        <div className="register-footer">
          Already have an account? <a href="/login">Login here</a>
        </div>
      </div>
    </div>
  );
}

export default StudentRegister;
```

### 4.2.3 Protected Routes

```javascript
import { Navigate } from 'react-router-dom';

function ProtectedRoute({ children }) {
  const token = localStorage.getItem('token');
  const user = JSON.parse(localStorage.getItem('user') || '{}');

  if (!token || user.role !== 'student') {
    return <Navigate to="/login" replace />;
  }

  return children;
}

export default ProtectedRoute;
```

### 4.2.4 Axios Configuration

```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:5000/api'
});

// Add token to all requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
```

### 4.2.5 Token Monitor Hook

```javascript
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { jwtDecode } from 'jwt-decode';

function useAuth() {
  const navigate = useNavigate();

  useEffect(() => {
    const checkAuth = () => {
      const token = localStorage.getItem('token');

      if (!token) {
        navigate('/login');
        return;
      }

      try {
        const decoded = jwtDecode(token);
        if (decoded.exp * 1000 < Date.now()) {
          localStorage.clear();
          navigate('/login');
        }
      } catch {
        localStorage.clear();
        navigate('/login');
      }
    };

    checkAuth();
    const interval = setInterval(checkAuth, 60000);

    return () => clearInterval(interval);
  }, [navigate]);
}

export default useAuth;
```

---

## 4.3 Home Page

```javascript
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../utils/api';
import useAuth from '../hooks/useAuth';

function HomePage() {
  useAuth(); // Monitor authentication

  const [stats, setStats] = useState(null);
  const [classes, setClasses] = useState([]);
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem('user'));

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [historyRes, classesRes] = await Promise.all([
        api.get('/student/attendance/history?limit=5'),
        api.get('/student/classes')
      ]);

      setStats(historyRes.data.statistics);
      setClasses(classesRes.data.classes);
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  };

  const handleLogout = () => {
    localStorage.clear();
    navigate('/login');
  };

  return (
    <div className="home-page">
      <header className="home-header">
        <div>
          <h1>Welcome, {user.name}</h1>
          <p className="roll-number">{user.rollNumber}</p>
        </div>
        <button onClick={handleLogout} className="btn-logout">
          Logout
        </button>
      </header>

      <div className="home-content">
        <div className="stats-card">
          <h2>Attendance Statistics</h2>
          {stats && (
            <div className="stats-grid">
              <div className="stat-item">
                <span className="stat-value">{stats.attended}</span>
                <span className="stat-label">Classes Attended</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">{stats.totalSessions}</span>
                <span className="stat-label">Total Sessions</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">{stats.percentage}%</span>
                <span className="stat-label">Attendance Rate</span>
              </div>
            </div>
          )}
        </div>

        <div className="action-card">
          <h2>Mark Attendance</h2>
          <p>Verify your face and scan QR code to mark attendance</p>
          <button 
            onClick={() => navigate('/mark-attendance')}
            className="btn-primary btn-large"
          >
            Start Attendance Process
          </button>
        </div>

        <div className="classes-card">
          <h2>My Classes</h2>
          <div className="classes-list">
            {classes.map(cls => (
              <div key={cls.id} className="class-item">
                <div>
                  <h3>{cls.className}</h3>
                  <p>{cls.courseCode}</p>
                  <p className="instructor">Instructor: {cls.instructorName}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="quick-links">
          <a href="/attendance-history" className="link-card">
            <span className="icon">📊</span>
            <span>View History</span>
          </a>
          <a href="/profile" className="link-card">
            <span className="icon">👤</span>
            <span>Profile</span>
          </a>
        </div>
      </div>
    </div>
  );
}

export default HomePage;
```

---

## 4.4 Mark Attendance Flow

### 4.4.1 Attendance Flow Component

```javascript
import React, { useState } from 'react';
import FaceVerification from '../components/FaceVerification';
import QRScanner from '../components/QRScanner';
import api from '../utils/api';

function MarkAttendance() {
  const [step, setStep] = useState('face'); // 'face', 'qr', 'success'
  const [faceVerified, setFaceVerified] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const handleFaceVerified = () => {
    setFaceVerified(true);
    setStep('qr');
  };

  const handleQRScanned = async (qrToken) => {
    try {
      const response = await api.post('/student/attendance/mark', {
        qrToken: qrToken,
        faceVerified: true
      });

      setResult(response.data.attendance);
      setStep('success');
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to mark attendance');
      setTimeout(() => setError(''), 5000);
    }
  };

  return (
    <div className="attendance-flow">
      <div className="flow-header">
        <h1>Mark Attendance</h1>
        <div className="steps-indicator">
          <div className={`step ${step === 'face' ? 'active' : faceVerified ? 'completed' : ''}`}>
            <span className="step-number">1</span>
            <span className="step-label">Face Verification</span>
          </div>
          <div className={`step ${step === 'qr' ? 'active' : step === 'success' ? 'completed' : ''}`}>
            <span className="step-number">2</span>
            <span className="step-label">Scan QR Code</span>
          </div>
          <div className={`step ${step === 'success' ? 'active' : ''}`}>
            <span className="step-number">3</span>
            <span className="step-label">Confirmation</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}

      <div className="flow-content">
        {step === 'face' && (
          <FaceVerification onSuccess={handleFaceVerified} />
        )}

        {step === 'qr' && (
          <QRScanner onScanSuccess={handleQRScanned} />
        )}

        {step === 'success' && (
          <div className="success-screen">
            <div className="success-icon">✓</div>
            <h2>Attendance Marked Successfully!</h2>
            <div className="success-details">
              <p><strong>Class:</strong> {result.className}</p>
              <p><strong>Time:</strong> {new Date(result.markedAt).toLocaleString()}</p>
            </div>
            <button onClick={() => window.location.href = '/home'}>
              Back to Home
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default MarkAttendance;
```

### 4.4.2 Face Verification Component

```javascript
import React, { useState, useRef, useEffect } from 'react';
import Webcam from 'react-webcam';
import api from '../utils/api';

function FaceVerification({ onSuccess }) {
  const webcamRef = useRef(null);
  const [capturing, setCapturing] = useState(false);
  const [error, setError] = useState('');

  const captureAndVerify = async () => {
    setCapturing(true);
    setError('');

    try {
      const imageSrc = webcamRef.current.getScreenshot();

      if (!imageSrc) {
        throw new Error('Failed to capture image');
      }

      const response = await api.post('/student/face/verify', {
        image: imageSrc
      });

      if (response.data.verified) {
        onSuccess();
      } else {
        setError(response.data.reason || 'Face verification failed. Please try again.');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Verification failed. Please try again.');
    } finally {
      setCapturing(false);
    }
  };

  return (
    <div className="face-verification">
      <h2>Step 1: Face Verification</h2>
      <p>Position your face in the frame and click "Verify Face"</p>

      <div className="camera-container">
        <Webcam
          ref={webcamRef}
          audio={false}
          screenshotFormat="image/jpeg"
          className="webcam"
          videoConstraints={{
            width: 640,
            height: 480,
            facingMode: 'user'
          }}
        />
        <div className="face-overlay"></div>
      </div>

      {error && (
        <div className="error-message">{error}</div>
      )}

      <button 
        onClick={captureAndVerify}
        disabled={capturing}
        className="btn-primary"
      >
        {capturing ? 'Verifying...' : 'Verify Face'}
      </button>

      <div className="tips">
        <h4>Tips for better verification:</h4>
        <ul>
          <li>Ensure good lighting</li>
          <li>Look directly at camera</li>
          <li>Remove glasses if possible</li>
          <li>Keep face centered in frame</li>
        </ul>
      </div>
    </div>
  );
}

export default FaceVerification;
```

### 4.4.3 QR Scanner Component

```javascript
import React, { useEffect, useState } from 'react';
import { Html5QrcodeScanner } from 'html5-qrcode';

function QRScanner({ onScanSuccess }) {
  const [scanning, setScanning] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const scanner = new Html5QrcodeScanner(
      'qr-reader',
      { 
        fps: 10,
        qrbox: { width: 250, height: 250 },
        aspectRatio: 1.0
      },
      false
    );

    scanner.render(
      (decodedText) => {
        scanner.clear();
        setScanning(false);
        onScanSuccess(decodedText);
      },
      (error) => {
        // Ignore continuous scan errors
      }
    );

    return () => {
      scanner.clear().catch(console.error);
    };
  }, [onScanSuccess]);

  return (
    <div className="qr-scanner">
      <h2>Step 2: Scan QR Code</h2>
      <p>Point your camera at the QR code displayed by your instructor</p>

      <div id="qr-reader" className="qr-reader"></div>

      {scanning && (
        <div className="scanning-indicator">
          <div className="spinner"></div>
          <p>Scanning for QR code...</p>
        </div>
      )}

      {error && (
        <div className="error-message">{error}</div>
      )}

      <div className="instructions">
        <h4>Instructions:</h4>
        <ul>
          <li>Hold your device steady</li>
          <li>Ensure QR code is clearly visible</li>
          <li>Scan the QR code from instructor's screen</li>
          <li>Do not use screenshots</li>
        </ul>
      </div>
    </div>
  );
}

export default QRScanner;
```

---

## 4.5 Attendance History Page

```javascript
import React, { useState, useEffect } from 'react';
import api from '../utils/api';

function AttendanceHistory() {
  const [attendance, setAttendance] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const response = await api.get('/student/attendance/history');
      setAttendance(response.data.attendance);
      setStats(response.data.statistics);
    } catch (error) {
      console.error('Error fetching history:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  return (
    <div className="history-page">
      <header className="page-header">
        <h1>Attendance History</h1>
        <a href="/home" className="btn-back">← Back</a>
      </header>

      {stats && (
        <div className="stats-summary">
          <div className="stat-box">
            <span className="stat-number">{stats.attended}</span>
            <span className="stat-text">Attended</span>
          </div>
          <div className="stat-box">
            <span className="stat-number">{stats.totalSessions}</span>
            <span className="stat-text">Total</span>
          </div>
          <div className="stat-box">
            <span className="stat-number">{stats.percentage}%</span>
            <span className="stat-text">Rate</span>
          </div>
        </div>
      )}

      <div className="history-list">
        {attendance.length === 0 ? (
          <p className="no-data">No attendance records found</p>
        ) : (
          <table className="history-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Class</th>
                <th>Subject</th>
                <th>Time</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {attendance.map((record, index) => (
                <tr key={index}>
                  <td>{new Date(record.markedAt).toLocaleDateString()}</td>
                  <td>{record.className}</td>
                  <td>{record.subject}</td>
                  <td>{new Date(record.markedAt).toLocaleTimeString()}</td>
                  <td>
                    <span className="status-badge present">Present</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default AttendanceHistory;
```

---

## 4.6 App Routes

```javascript
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import StudentLogin from './pages/Login';
import StudentRegister from './pages/Register';
import HomePage from './pages/Home';
import MarkAttendance from './pages/MarkAttendance';
import AttendanceHistory from './pages/AttendanceHistory';
import Profile from './pages/Profile';
import ProtectedRoute from './components/ProtectedRoute';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<StudentLogin />} />
        <Route path="/register" element={<StudentRegister />} />
        
        <Route path="/home" element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        } />
        
        <Route path="/mark-attendance" element={
          <ProtectedRoute>
            <MarkAttendance />
          </ProtectedRoute>
        } />
        
        <Route path="/attendance-history" element={
          <ProtectedRoute>
            <AttendanceHistory />
          </ProtectedRoute>
        } />
        
        <Route path="/profile" element={
          <ProtectedRoute>
            <Profile />
          </ProtectedRoute>
        } />
        
        <Route path="/" element={<Navigate to="/home" />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
```

---

## 4.7 File Structure

```
student-app/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── ProtectedRoute.jsx
│   │   ├── FaceVerification.jsx
│   │   └── QRScanner.jsx
│   ├── pages/
│   │   ├── Login.jsx
│   │   ├── Register.jsx
│   │   ├── Home.jsx
│   │   ├── MarkAttendance.jsx
│   │   ├── AttendanceHistory.jsx
│   │   └── Profile.jsx
│   ├── hooks/
│   │   └── useAuth.js
│   ├── utils/
│   │   └── api.js
│   ├── App.jsx
│   ├── index.js
│   └── styles.css
├── package.json
└── .env
```

---

## 4.8 Security Features

**Implemented:**
- ✓ JWT token authentication
- ✓ Secure token storage
- ✓ Auto logout on token expiry
- ✓ Protected routes with role check
- ✓ Request interceptors for auth
- ✓ Response interceptors for 401 handling
- ✓ Password validation on registration
- ✓ HTTPS enforcement (production)
- ✓ XSS protection via React
- ✓ Camera permission handling

