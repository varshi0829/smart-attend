# SmartAttend - Service Startup Guide

**Complete setup guide for running the Smart Attendance System locally or on LAN.**

---

## 📋 Prerequisites

### 1. System Requirements
- **Node.js:** v18+ ([Download](https://nodejs.org/))
- **Python:** v3.11 or v3.12 (v3.13 has limited TensorFlow support)
- **MongoDB:** Local installation OR MongoDB Atlas account (free tier)
- **Git:** For cloning the repository

### 2. Check Your Setup
```bash
node --version    # Should show v18+
python3 --version # Should show 3.11.x or 3.12.x
mongod --version  # If using local MongoDB
```

---

## 🚀 First-Time Setup

### Step 1: Clone & Navigate
```bash
git clone <repository-url>
cd smart-attend
```

### Step 2: Configure MongoDB

#### Option A: MongoDB Atlas (Recommended - Free Cloud)
1. Follow the guide: [MONGODB_ATLAS_SETUP.md](./MONGODB_ATLAS_SETUP.md)
2. Copy your connection string (looks like: `mongodb+srv://user:pass@cluster.mongodb.net/...`)

#### Option B: Local MongoDB
1. Install MongoDB Community Edition
2. Start MongoDB: `sudo systemctl start mongod` (Linux) or `brew services start mongodb-community` (Mac)
3. Your connection string: `mongodb://localhost:27017/smartattend`

### Step 3: Configure Backend Environment
```bash
cd backend
cp .env.example .env  # If .env.example doesn't exist, create .env manually
```

Edit `backend/.env`:
```env
PORT=5000
MONGODB_URI=mongodb+srv://your-connection-string-here
JWT_SECRET=your-super-secret-key-change-this-in-production
NODE_ENV=development
```

### Step 4: Install Backend Dependencies
```bash
# From backend/ directory
npm install
```

### Step 5: Setup Python Services

#### Face Recognition Service
```bash
cd ../face-service
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Note:** If you encounter TensorFlow version errors with Python 3.13, use Python 3.11 or 3.12:
```bash
# Install Python 3.12 if needed, then:
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### QR Service
```bash
cd ../qr-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Attendance Service
```bash
cd ../attendance-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 6: Generate SSL Certificates (Required for Camera Access)

**Why?** Modern browsers require HTTPS to access camera/webcam.

```bash
# From project root directory
cd smart-attend

# Find your local IP address:
# Linux/Mac: ip addr show | grep inet
# Windows: ipconfig

# Generate certificate (replace 192.168.1.100 with YOUR IP)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=192.168.1.100"
```

**Important:** Use your actual LAN IP address, not localhost or 127.0.0.1!

---

## ▶️ Running the System

You need **6 terminal windows** (or use `tmux`/`screen` for advanced users).

### Terminal 1: Backend API Server (Port 5000)
```bash
cd backend
npm start
# You should see: "✓ Server running on port 5000" and "✓ MongoDB connected"
```

### Terminal 2: Face Recognition Service (Port 5001)
```bash
cd face-service
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 5001 --ssl-keyfile ../key.pem --ssl-certfile ../cert.pem
```

### Terminal 3: QR Service (Port 5002)
```bash
cd qr-service
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 5002 --ssl-keyfile ../key.pem --ssl-certfile ../cert.pem
```

### Terminal 4: Attendance Orchestrator (Port 5003)
```bash
cd attendance-service
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 5003 --ssl-keyfile ../key.pem --ssl-certfile ../cert.pem
```

### Terminal 5: Student Frontend (Port 8001)
```bash
# From project root
npx http-server ./frontend-student -p 8001 --ssl --cert cert.pem --key key.pem
```

### Terminal 6: Instructor Frontend (Port 8002)
```bash
# From project root
npx http-server ./frontend-instructor -p 8002 --ssl --cert cert.pem --key key.pem
```

---

## 🌐 Accessing the Application

### On the Same Machine
- **Student Portal:** `https://localhost:8001`
- **Instructor Portal:** `https://localhost:8002`
- **Backend API:** `http://localhost:5000`

### On LAN (Other Devices)
Replace `localhost` with your machine's IP address (e.g., `192.168.1.100`):
- **Student Portal:** `https://192.168.1.100:8001`
- **Instructor Portal:** `https://192.168.1.100:8002`

### ⚠️ Certificate Warning (First Time Only)
Since we're using self-signed certificates, browsers will show a security warning.

**You MUST accept the certificate for EACH service:**
1. Visit `https://YOUR-IP:8001` → Click "Advanced" → "Proceed to site"
2. Visit `https://YOUR-IP:8002` → Click "Advanced" → "Proceed to site"
3. Visit `https://YOUR-IP:5001/docs` → Accept certificate
4. Visit `https://YOUR-IP:5002/docs` → Accept certificate
5. Visit `https://YOUR-IP:5003/docs` → Accept certificate

**Do this on every device that will access the system.**

---

## 🧪 Testing the Setup

### 1. Check All Services Are Running
```bash
# Backend
curl http://localhost:5000/health
# Should return: {"status":"ok","message":"Server is running"}

# Face Service
curl -k https://localhost:5001/health
# Should return: {"status":"healthy"}

# QR Service
curl -k https://localhost:5002/health
# Should return: {"status":"healthy"}

# Attendance Service
curl -k https://localhost:5003/health
# Should return: {"status":"healthy"}
```

### 2. Create Test Users
```bash
# Register an instructor
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "instructor@test.com",
    "password": "test123",
    "name": "Test Instructor",
    "role": "instructor"
  }'

# Register a student
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "student@test.com",
    "password": "test123",
    "name": "Test Student",
    "rollNumber": "24WH1A0501",
    "role": "student"
  }'
```

### 3. Test Login
```bash
# Login as instructor
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "instructor@test.com",
    "password": "test123"
  }'
# Copy the "token" from the response
```

---

## 🛠️ Troubleshooting

### MongoDB Connection Failed
- **Atlas:** Check your IP is whitelisted (0.0.0.0/0 for testing)
- **Local:** Ensure MongoDB service is running: `sudo systemctl status mongod`

### Python Package Installation Errors
- **TensorFlow:** Use Python 3.11 or 3.12, NOT 3.13
- **OpenCV:** Install system dependencies: `sudo apt-get install libgl1-mesa-glx` (Linux)

### Port Already in Use
```bash
# Find what's using the port (e.g., 5000)
lsof -i :5000
# Kill the process
kill -9 <PID>
```

### Camera Not Working
- **HTTPS Required:** Ensure you're using `https://` not `http://`
- **Certificate:** Accept the self-signed certificate in browser
- **Permissions:** Allow camera access when browser prompts

### CORS Errors
- Ensure backend is running on port 5000
- Check frontend is making requests to correct backend URL
- Verify CORS is enabled in `backend/server.js`

---

## 📱 Alternative: Using Localtunnel (No SSL Setup)

If SSL certificate setup is problematic, use localtunnel to expose services:

```bash
# Install localtunnel globally
npm install -g localtunnel

# In separate terminals, expose each service:
lt --port 5000  # Backend
lt --port 5001  # Face Service
lt --port 5002  # QR Service
lt --port 5003  # Attendance Service
lt --port 8001  # Student Frontend
lt --port 8002  # Instructor Frontend
```

Each command will give you a public URL (e.g., `https://random-name.loca.lt`). Update the API URLs in frontend HTML files to use these URLs.

---

## 📚 Additional Resources

- **System Architecture:** [docs/0002_architecture.md](./docs/0002_architecture.md)
- **API Documentation:** [docs/0008_api_specifications.md](./docs/0008_api_specifications.md)
- **Testing Guide:** [TESTING_GUIDE.md](./TESTING_GUIDE.md)
- **Implementation Guide:** [IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md)

---

## 🎯 Quick Start Checklist

- [ ] Node.js and Python installed
- [ ] MongoDB configured (Atlas or Local)
- [ ] Backend `.env` file created with MongoDB URI
- [ ] All Python virtual environments created and dependencies installed
- [ ] SSL certificates generated with your LAN IP
- [ ] All 6 services running in separate terminals
- [ ] Certificates accepted in browser for all ports
- [ ] Test users created and login working
- [ ] Camera access working in browser

---

**Need Help?** Check the troubleshooting section or open an issue in the repository.

**Last Updated:** March 8, 2026
