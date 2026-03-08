# MongoDB Atlas Setup Guide - Quick Start

## 🎯 Goal
Set up free MongoDB Atlas cloud database for your attendance system.

---

## Step 1: Create MongoDB Atlas Account (2 minutes)

1. Go to: https://www.mongodb.com/cloud/atlas/register
2. Sign up with:
   - Email
   - OR Google account
   - OR GitHub account
3. Verify your email if required

---

## Step 2: Create Free Cluster (3 minutes)

### After Login:

1. Click **"Build a Database"** or **"Create"**

2. Choose **M0 FREE** tier:
   - ✅ 512 MB Storage
   - ✅ Shared RAM
   - ✅ No credit card required

3. Select Cloud Provider & Region:
   - **Provider:** AWS (recommended)
   - **Region:** Choose closest to you (e.g., Mumbai for India, Singapore for Asia)
   - Keep default name or rename to: `attendance-cluster`

4. Click **"Create"**

**Wait 1-3 minutes for cluster creation...**

---

## Step 3: Create Database User (1 minute)

### Security Quickstart will appear:

1. **Authentication Method:** Username and Password

2. **Create User:**
   - Username: `attendanceUser`
   - Password: Click **"Autogenerate Secure Password"**
   - **IMPORTANT:** Copy and save this password! You'll need it.

3. Click **"Create User"**

**Example:**
```
Username: attendanceUser
Password: xK9mP2nQ7vL4sR8t  (your generated password will be different)
```

---

## Step 4: Add Your IP Address (1 minute)

### Network Access:

1. You'll see "Where would you like to connect from?"

2. Choose **"My Local Environment"**

3. Click **"Add My Current IP Address"**
   - It will auto-detect your IP
   - Description: `My Development Machine`

4. Click **"Add Entry"**

**Alternative (for testing only):**
- To allow from anywhere: `0.0.0.0/0`
- ⚠️ Not recommended for production!

5. Click **"Finish and Close"**

---

## Step 5: Get Connection String (2 minutes)

1. Click **"Connect"** button on your cluster

2. Choose **"Connect your application"**

3. Select:
   - **Driver:** Node.js
   - **Version:** 5.5 or later

4. Copy the connection string. It looks like:
```
mongodb+srv://attendanceUser:<password>@attendance-cluster.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

5. **IMPORTANT:** Replace `<password>` with your actual password from Step 3

**Example:**
```
mongodb+srv://attendanceUser:xK9mP2nQ7vL4sR8t@attendance-cluster.abc123.mongodb.net/?retryWrites=true&w=majority
```

---

## Step 6: Update Your .env File

### Replace your current MONGODB_URI:

**OLD:**
```env
MONGODB_URI=mongodb://localhost:27017/attendance_system
```

**NEW:**
```env
MONGODB_URI=mongodb+srv://attendanceUser:YOUR_PASSWORD_HERE@attendance-cluster.xxxxx.mongodb.net/attendance_system?retryWrites=true&w=majority
```

### Complete .env file should look like:

```env
PORT=5000
MONGODB_URI=mongodb+srv://attendanceUser:xK9mP2nQ7vL4sR8t@attendance-cluster.abc123.mongodb.net/attendance_system?retryWrites=true&w=majority
JWT_SECRET=your_super_secret_jwt_key_min_32_characters_long_change_this
NODE_ENV=development
```

**Key Points:**
- ✅ Added `/attendance_system` before the `?` to specify database name
- ✅ Replaced `<password>` with actual password
- ✅ Keep `?retryWrites=true&w=majority` at the end

---

## Step 7: Test Connection

### Run your server:

```bash
cd /home/cse/smart-attend/backend
npm run dev
```

### Expected Output:

```
✓ MongoDB connected
✓ Server running on port 5000
```

### If you see errors:

**Error: "Authentication failed"**
- Check password is correct (no spaces, exact match)
- Password should NOT have `<` or `>` symbols

**Error: "IP not whitelisted"**
- Go to Atlas → Network Access
- Add your current IP again

**Error: "Connection timeout"**
- Check your internet connection
- Try different region when creating cluster

---

## 🎉 Success Checklist

- ✅ MongoDB Atlas account created
- ✅ Free M0 cluster created
- ✅ Database user created
- ✅ IP address whitelisted
- ✅ Connection string copied
- ✅ .env file updated
- ✅ Server connects successfully

---

## 📝 Important Notes

### Connection String Format:
```
mongodb+srv://USERNAME:PASSWORD@CLUSTER.xxxxx.mongodb.net/DATABASE_NAME?options
```

### Parts Explained:
- `mongodb+srv://` - Protocol (Atlas uses SRV)
- `USERNAME` - Your database user (attendanceUser)
- `PASSWORD` - Your generated password
- `CLUSTER.xxxxx.mongodb.net` - Your cluster address
- `/DATABASE_NAME` - Your database name (attendance_system)
- `?retryWrites=true&w=majority` - Connection options

### Security Tips:
1. **Never commit .env to Git!**
   - Add `.env` to `.gitignore`

2. **Use strong passwords**
   - Use the auto-generated one

3. **Restrict IP access**
   - Only add your development IP
   - Add production server IP separately

4. **Rotate credentials**
   - Change password periodically

---

## 🔧 Troubleshooting

### Problem: Can't find connection string

**Solution:**
1. Go to Atlas Dashboard
2. Click "Database" in left menu
3. Click "Connect" on your cluster
4. Choose "Connect your application"
5. Copy the string

### Problem: Password has special characters

**Solution:**
If your password has special characters like `@`, `#`, `%`, etc., you need to URL encode them:
- `@` becomes `%40`
- `#` becomes `%23`
- `%` becomes `%25`

Or regenerate a simpler password.

### Problem: "MongooseServerSelectionError"

**Solution:**
1. Check internet connection
2. Verify IP is whitelisted
3. Check connection string is correct
4. Try adding `0.0.0.0/0` temporarily to test

---

## 🎯 Next Steps

Once MongoDB Atlas is connected:

1. ✅ Test health endpoint: `curl http://localhost:5000/health`
2. ✅ Test registration: Register instructor and student
3. ✅ Test login: Login with created users
4. ✅ Move to Phase 1B: Session & QR System

---

## 📱 MongoDB Atlas Dashboard

**Useful Features:**

1. **Collections Tab:**
   - View your data
   - See users, sessions, attendance records

2. **Metrics Tab:**
   - Monitor database usage
   - Check connection count

3. **Network Access:**
   - Manage IP whitelist

4. **Database Access:**
   - Manage users and passwords

**Access:** https://cloud.mongodb.com/

---

## ✅ Quick Reference

**Your Credentials (save these):**
```
Cluster Name: attendance-cluster
Username: attendanceUser
Password: [your generated password]
Database Name: attendance_system
Connection String: mongodb+srv://attendanceUser:PASSWORD@cluster.mongodb.net/attendance_system
```

**Ready to test? Run:**
```bash
npm run dev
```

**Should see:**
```
✓ MongoDB connected
✓ Server running on port 5000
```

🎉 **You're all set!**
