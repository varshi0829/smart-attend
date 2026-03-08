# Instructor Web Application Design
# Complete UI/UX and Authentication Flow

---

## 3.1 Application Overview

**Purpose:** Web application for instructors to manage attendance sessions

**Technology Stack:**
- React.js 18+ or Vue.js 3+
- React Router / Vue Router
- Axios for API calls
- Socket.io-client for real-time updates
- TailwindCSS / Material-UI for styling
- QRCode.js for QR generation

---

## 3.2 Authentication System

### 3.2.1 Login Flow

```
Landing Page → Login Form → Validate → Get JWT → Store Token → Dashboard
```

**Login Component:**
```javascript
import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

function InstructorLogin() {
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
        role: 'instructor'
      });

      // Store token
      localStorage.setItem('token', response.data.token);
      localStorage.setItem('user', JSON.stringify(response.data.user));

      // Redirect to dashboard
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.error || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <h1>Instructor Login</h1>
        <p>Smart Attendance System</p>

        {error && (
          <div className="error-message">{error}</div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({...formData, email: e.target.value})}
              required
              placeholder="instructor@university.edu"
            />
          </div>

          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({...formData, password: e.target.value})}
              required
              placeholder="Enter your password"
            />
          </div>

          <button type="submit" disabled={loading}>
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <div className="login-footer">
          <a href="/forgot-password">Forgot Password?</a>
        </div>
      </div>
    </div>
  );
}

export default InstructorLogin;
```

### 3.2.2 Protected Routes

**Route Guard:**
```javascript
import { Navigate } from 'react-router-dom';

function ProtectedRoute({ children }) {
  const token = localStorage.getItem('token');
  const user = JSON.parse(localStorage.getItem('user') || '{}');

  if (!token || user.role !== 'instructor') {
    return <Navigate to="/login" replace />;
  }

  return children;
}

export default ProtectedRoute;
```

**App Routes:**
```javascript
import { BrowserRouter, Routes, Route } from 'react-router-dom';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<InstructorLogin />} />
        
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        } />
        
        <Route path="/session/:id" element={
          <ProtectedRoute>
            <SessionPage />
          </ProtectedRoute>
        } />
        
        <Route path="/" element={<Navigate to="/dashboard" />} />
      </Routes>
    </BrowserRouter>
  );
}
```

### 3.2.3 Axios Interceptor

**Setup:**
```javascript
import axios from 'axios';

// Create axios instance
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:5000/api'
});

// Request interceptor - Add token to all requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - Handle token expiration
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
```

### 3.2.4 Auto Logout on Token Expiry

**Token Monitor:**
```javascript
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { jwtDecode } from 'jwt-decode';

function useTokenMonitor() {
  const navigate = useNavigate();

  useEffect(() => {
    const checkToken = () => {
      const token = localStorage.getItem('token');
      
      if (!token) {
        navigate('/login');
        return;
      }

      try {
        const decoded = jwtDecode(token);
        const currentTime = Date.now() / 1000;

        if (decoded.exp < currentTime) {
          // Token expired
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          navigate('/login');
        }
      } catch (error) {
        navigate('/login');
      }
    };

    // Check immediately
    checkToken();

    // Check every minute
    const interval = setInterval(checkToken, 60000);

    return () => clearInterval(interval);
  }, [navigate]);
}

export default useTokenMonitor;
```

---

## 3.3 Dashboard Page

### 3.3.1 Dashboard Component

```javascript
import React, { useState, useEffect } from 'react';
import api from '../utils/api';
import useTokenMonitor from '../hooks/useTokenMonitor';

function Dashboard() {
  useTokenMonitor(); // Monitor token expiry

  const [classes, setClasses] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const user = JSON.parse(localStorage.getItem('user'));

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [classesRes, sessionsRes] = await Promise.all([
        api.get('/instructor/classes'),
        api.get('/instructor/sessions?limit=10')
      ]);

      setClasses(classesRes.data.classes);
      setSessions(sessionsRes.data.sessions);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleStartSession = async (classId, className) => {
    try {
      const response = await api.post('/instructor/session/start', {
        classId,
        className,
        subject: ''
      });

      // Navigate to session page
      window.location.href = `/session/${response.data.session.id}`;
    } catch (error) {
      alert('Failed to start session');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/login';
  };

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>Instructor Dashboard</h1>
        <div className="user-info">
          <span>Welcome, {user.name}</span>
          <button onClick={handleLogout}>Logout</button>
        </div>
      </header>

      <div className="dashboard-content">
        <section className="classes-section">
          <h2>My Classes</h2>
          <div className="classes-grid">
            {classes.map(cls => (
              <div key={cls.id} className="class-card">
                <h3>{cls.className}</h3>
                <p>{cls.courseCode}</p>
                <p>{cls.studentCount} students</p>
                <button onClick={() => handleStartSession(cls.id, cls.className)}>
                  Start Session
                </button>
              </div>
            ))}
          </div>
        </section>

        <section className="recent-sessions">
          <h2>Recent Sessions</h2>
          <table>
            <thead>
              <tr>
                <th>Class</th>
                <th>Date</th>
                <th>Status</th>
                <th>Present</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map(session => (
                <tr key={session.id}>
                  <td>{session.className}</td>
                  <td>{new Date(session.startTime).toLocaleString()}</td>
                  <td>
                    <span className={`status ${session.status}`}>
                      {session.status}
                    </span>
                  </td>
                  <td>{session.presentCount}</td>
                  <td>
                    <a href={`/session/${session.id}`}>View</a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}

export default Dashboard;
```

---

## 3.4 Session Page

### 3.4.1 Session Component

```javascript
import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import io from 'socket.io-client';
import api from '../utils/api';

function SessionPage() {
  const { id } = useParams();
  const [session, setSession] = useState(null);
  const [attendance, setAttendance] = useState([]);
  const [qrCode, setQrCode] = useState(null);
  const [timeLeft, setTimeLeft] = useState(45);
  const [socket, setSocket] = useState(null);

  useEffect(() => {
    fetchSession();
    initializeWebSocket();

    return () => {
      if (socket) socket.disconnect();
    };
  }, [id]);

  const fetchSession = async () => {
    try {
      const response = await api.get(`/instructor/session/${id}`);
      setSession(response.data.session);
      setAttendance(response.data.attendance);
      
      // Fetch QR code
      const qrResponse = await api.get(`/instructor/session/${id}/qr`);
      setQrCode(qrResponse.data.qrCode);
    } catch (error) {
      console.error('Error fetching session:', error);
    }
  };

  const initializeWebSocket = () => {
    const token = localStorage.getItem('token');
    const newSocket = io(process.env.REACT_APP_WS_URL, {
      auth: { token }
    });

    newSocket.emit('join_session', { sessionId: id });

    newSocket.on('qr_refresh', (data) => {
      setQrCode(data.qrCode);
      setTimeLeft(45);
    });

    newSocket.on('attendance_marked', (data) => {
      setAttendance(prev => [...prev, data.student]);
      setSession(prev => ({
        ...prev,
        presentCount: prev.presentCount + 1
      }));
    });

    setSocket(newSocket);
  };

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft(prev => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(timer);
  }, [qrCode]);

  const handleStopSession = async () => {
    if (!window.confirm('Are you sure you want to stop this session?')) {
      return;
    }

    try {
      await api.post(`/instructor/session/${id}/stop`);
      setSession(prev => ({ ...prev, status: 'stopped' }));
      alert('Session stopped successfully');
    } catch (error) {
      alert('Failed to stop session');
    }
  };

  if (!session) {
    return <div className="loading">Loading...</div>;
  }

  return (
    <div className="session-page">
      <header className="session-header">
        <div>
          <h1>{session.className}</h1>
          <p>{session.subject}</p>
        </div>
        <div className="session-status">
          <span className={`status ${session.status}`}>
            {session.status.toUpperCase()}
          </span>
        </div>
      </header>

      <div className="session-content">
        <div className="qr-section">
          <h2>QR Code for Attendance</h2>
          
          {session.status === 'active' ? (
            <>
              {qrCode && (
                <div className="qr-display">
                  <img src={qrCode} alt="QR Code" />
                  <div className="qr-timer">
                    <p>Refreshes in: <strong>{timeLeft}s</strong></p>
                    <div className="progress-bar">
                      <div 
                        className="progress" 
                        style={{ width: `${(timeLeft / 45) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              )}
              
              <button 
                onClick={handleStopSession}
                className="btn-danger"
              >
                Stop Session
              </button>
            </>
          ) : (
            <div className="session-stopped">
              <p>Session has been stopped</p>
              <p>Final Count: {session.presentCount} students</p>
            </div>
          )}
        </div>

        <div className="attendance-section">
          <h2>Live Attendance ({attendance.length})</h2>
          
          <div className="attendance-list">
            {attendance.length === 0 ? (
              <p className="no-attendance">No attendance marked yet</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Roll Number</th>
                    <th>Name</th>
                    <th>Time</th>
                    <th>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {attendance.map((student, index) => (
                    <tr key={student.studentId}>
                      <td>{index + 1}</td>
                      <td>{student.rollNumber}</td>
                      <td>{student.name}</td>
                      <td>{new Date(student.markedAt).toLocaleTimeString()}</td>
                      <td>{(student.confidence * 100).toFixed(0)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default SessionPage;
```

---

## 3.5 Styling (TailwindCSS Example)

```css
/* Login Page */
.login-container {
  @apply min-h-screen flex items-center justify-center bg-gray-100;
}

.login-card {
  @apply bg-white p-8 rounded-lg shadow-lg w-full max-w-md;
}

.login-card h1 {
  @apply text-2xl font-bold text-center mb-2;
}

.login-card p {
  @apply text-gray-600 text-center mb-6;
}

.error-message {
  @apply bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4;
}

.form-group {
  @apply mb-4;
}

.form-group label {
  @apply block text-gray-700 font-medium mb-2;
}

.form-group input {
  @apply w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500;
}

button[type="submit"] {
  @apply w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:bg-gray-400;
}

/* Dashboard */
.dashboard-header {
  @apply flex justify-between items-center p-6 bg-white shadow;
}

.classes-grid {
  @apply grid grid-cols-1 md:grid-cols-3 gap-4 mt-4;
}

.class-card {
  @apply bg-white p-6 rounded-lg shadow hover:shadow-lg transition;
}

/* Session Page */
.qr-display {
  @apply flex flex-col items-center;
}

.qr-display img {
  @apply w-64 h-64 border-4 border-gray-300 rounded-lg;
}

.progress-bar {
  @apply w-full bg-gray-200 rounded-full h-2 mt-2;
}

.progress {
  @apply bg-blue-600 h-2 rounded-full transition-all duration-1000;
}

.status.active {
  @apply bg-green-100 text-green-800 px-3 py-1 rounded-full;
}

.status.stopped {
  @apply bg-red-100 text-red-800 px-3 py-1 rounded-full;
}
```

---

## 3.6 Environment Configuration

**.env file:**
```
REACT_APP_API_URL=http://localhost:5000/api
REACT_APP_WS_URL=http://localhost:5000
```

---

## 3.7 Complete File Structure

```
instructor-app/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── ProtectedRoute.jsx
│   │   └── QRDisplay.jsx
│   ├── pages/
│   │   ├── Login.jsx
│   │   ├── Dashboard.jsx
│   │   └── SessionPage.jsx
│   ├── hooks/
│   │   └── useTokenMonitor.js
│   ├── utils/
│   │   └── api.js
│   ├── App.jsx
│   ├── index.js
│   └── styles.css
├── package.json
└── .env
```

---

## 3.8 Security Features

**Implemented:**
- ✓ JWT token storage in localStorage
- ✓ Automatic token attachment to requests
- ✓ Token expiry monitoring
- ✓ Auto logout on expiry
- ✓ Protected routes
- ✓ Role verification
- ✓ HTTPS enforcement (production)
- ✓ XSS protection via React
- ✓ CSRF protection via token

