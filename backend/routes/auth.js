const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { OAuth2Client } = require('google-auth-library');
const User = require('../models/User');

const router = express.Router();
const googleClient = new OAuth2Client(process.env.GOOGLE_CLIENT_ID);

// Register (Local auth - for instructors mainly)
router.post('/register', async (req, res) => {
  try {
    const { email, password, role, name, rollNumber, department, phone } = req.body;
    
    // Input validation
    if (!email || !password || !role || !name) {
      return res.status(400).json({ error: 'Missing required fields' });
    }
    
    const VALID_ROLES = ['instructor', 'student', 'faculty', 'hod', 'principal'];
    if (!VALID_ROLES.includes(role)) {
      return res.status(400).json({ error: `Invalid role. Must be one of: ${VALID_ROLES.join(', ')}` });
    }

    if (role === 'student' && !rollNumber) {
      return res.status(400).json({ error: 'Roll number is required for students' });
    }

    if (['hod', 'faculty', 'instructor'].includes(role) && !department) {
      return res.status(400).json({ error: 'Department is required for faculty/HOD roles' });
    }

    const existingUser = await User.findOne({ email });
    if (existingUser) {
      return res.status(400).json({ error: 'Email already registered' });
    }

    const hashedPassword = await bcrypt.hash(password, 10);

    const { isClassTeacher, assignedYear, assignedSection } = req.body;
    const assignedClass = (isClassTeacher && (role === 'faculty' || role === 'instructor'))
      ? { isClassTeacher: true, year: assignedYear, section: assignedSection }
      : { isClassTeacher: false };

    const user = await User.create({
      email,
      password: hashedPassword,
      role,
      name,
      rollNumber,
      department,
      phone,
      assignedClass,
      authProvider: 'local'
    });
    
    res.status(201).json({
      success: true,
      message: 'User registered successfully',
      user: {
        id: user._id,
        email: user.email,
        role: user.role,
        name: user.name
      }
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Login (Local auth)
router.post('/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    
    // Input validation
    if (!email || !password) {
      return res.status(400).json({ error: 'Email and password are required' });
    }
    
    // Find user by email only (don't require role from frontend)
    const user = await User.findOne({ email });
    if (!user) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    // Check if account is active
    if (!user.isActive) {
      return res.status(403).json({ error: 'Account is inactive' });
    }
    
    // Check if user has password (local auth)
    if (!user.password) {
      return res.status(400).json({ error: 'Please use Google Sign-In for this account' });
    }
    
    const isValidPassword = await bcrypt.compare(password, user.password);
    if (!isValidPassword) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    const token = jwt.sign(
      { userId: user._id, role: user.role, department: user.department, assignedClass: user.assignedClass },
      process.env.JWT_SECRET,
      { expiresIn: '24h' }
    );
    
    res.json({
      success: true,
      token,
      user: {
        id: user._id,
        email: user.email,
        role: user.role,
        name: user.name,
        rollNumber: user.rollNumber,
        authProvider: user.authProvider
      }
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Google Sign-In
router.post('/google', async (req, res) => {
  try {
    const { credential } = req.body;
    
    if (!credential) {
      return res.status(400).json({ error: 'Google credential is required' });
    }
    
    // Verify Google token
    const ticket = await googleClient.verifyIdToken({
      idToken: credential,
      audience: process.env.GOOGLE_CLIENT_ID
    });
    
    const payload = ticket.getPayload();
    const { sub: googleId, email, name, picture } = payload;
    
    // Check domain
    const emailDomain = email.split('@')[1];
    if (emailDomain !== process.env.ALLOWED_DOMAIN) {
      return res.status(403).json({ 
        error: `Only ${process.env.ALLOWED_DOMAIN} accounts are allowed` 
      });
    }
    
    // Find user in database
    let user = await User.findOne({ email });
    
    if (!user) {
      return res.status(404).json({ 
        error: 'User not found. Please contact administrator to add your account.' 
      });
    }
    
    // Check if account is active
    if (!user.isActive) {
      return res.status(403).json({ error: 'Account is inactive' });
    }
    
    // Update Google ID if first time Google login
    if (!user.googleId) {
      user.googleId = googleId;
      user.authProvider = 'google';
      user.profilePicture = picture;
      await user.save();
    }
    
    // Generate JWT
    const token = jwt.sign(
      { userId: user._id, role: user.role, department: user.department, assignedClass: user.assignedClass },
      process.env.JWT_SECRET,
      { expiresIn: '24h' }
    );
    
    res.json({
      success: true,
      token,
      user: {
        id: user._id,
        email: user.email,
        role: user.role,
        name: user.name,
        rollNumber: user.rollNumber,
        authProvider: user.authProvider,
        profilePicture: user.profilePicture
      }
    });
    
  } catch (error) {
    console.error('Google auth error:', error);
    
    if (error.message.includes('Token used too late')) {
      return res.status(401).json({ error: 'Google token expired. Please try again.' });
    }
    
    res.status(500).json({ error: 'Google authentication failed' });
  }
});

module.exports = router;
