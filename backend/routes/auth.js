const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { OAuth2Client } = require('google-auth-library');
const { randomUUID } = require('crypto');
const pool = require('../config/db');

const router = express.Router();
const googleClient = new OAuth2Client(process.env.GOOGLE_CLIENT_ID);

function makeToken(user) {
  return jwt.sign(
    {
      userId: user.id,
      role: user.role,
      department: user.department,
      assignedClass: {
        isClassTeacher: user.is_class_teacher,
        year: user.assigned_year,
        section: user.assigned_section
      }
    },
    process.env.JWT_SECRET,
    { expiresIn: '24h' }
  );
}

function safeUser(u) {
  return {
    id: u.id,
    email: u.email,
    role: u.role,
    name: u.name,
    department: u.department,
    rollNumber: u.roll_number,
    authProvider: u.auth_provider,
    profilePicture: u.profile_picture,
    assignedClass: {
      isClassTeacher: u.is_class_teacher,
      year: u.assigned_year,
      section: u.assigned_section
    }
  };
}

// Register
router.post('/register', async (req, res) => {
  try {
    const { email, password, role, name, rollNumber, department, phone } = req.body;

    if (!email || !password || !role || !name) {
      return res.status(400).json({ error: 'Missing required fields' });
    }
    if (!['instructor', 'faculty', 'student', 'hod', 'principal'].includes(role)) {
      return res.status(400).json({ error: 'Invalid role' });
    }
    if (role === 'student' && !rollNumber) {
      return res.status(400).json({ error: 'Roll number is required for students' });
    }

    const exists = await pool.query('SELECT id FROM users WHERE email = $1', [email]);
    if (exists.rows[0]) return res.status(400).json({ error: 'Email already registered' });

    const hashedPassword = await bcrypt.hash(password, 10);
    const id = randomUUID();

    await pool.query(
      `INSERT INTO users (id, email, password, role, name, roll_number, department, phone)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
      [id, email, hashedPassword, role, name, rollNumber || null, department || null, phone || null]
    );

    const { rows } = await pool.query('SELECT * FROM users WHERE id = $1', [id]);
    res.status(201).json({ success: true, message: 'User registered successfully', user: safeUser(rows[0]) });
  } catch (error) {
    console.error('Register error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Login
router.post('/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    if (!email || !password) return res.status(400).json({ error: 'Email and password are required' });

    const { rows } = await pool.query('SELECT * FROM users WHERE email = $1', [email]);
    const user = rows[0];
    if (!user) return res.status(401).json({ error: 'Invalid credentials' });
    if (!user.is_active) return res.status(403).json({ error: 'Account is inactive' });
    if (!user.password) return res.status(400).json({ error: 'Please use Google Sign-In for this account' });

    const valid = await bcrypt.compare(password, user.password);
    if (!valid) return res.status(401).json({ error: 'Invalid credentials' });

    res.json({ success: true, token: makeToken(user), user: safeUser(user) });
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Google Sign-In
router.post('/google', async (req, res) => {
  try {
    const { credential } = req.body;
    if (!credential) return res.status(400).json({ error: 'Google credential is required' });

    const ticket = await googleClient.verifyIdToken({
      idToken: credential,
      audience: process.env.GOOGLE_CLIENT_ID
    });
    const { sub: googleId, email, name, picture } = ticket.getPayload();

    const emailDomain = email.split('@')[1];
    if (emailDomain !== process.env.ALLOWED_DOMAIN) {
      return res.status(403).json({ error: `Only ${process.env.ALLOWED_DOMAIN} accounts are allowed` });
    }

    let { rows } = await pool.query('SELECT * FROM users WHERE email = $1', [email]);
    let user = rows[0];

    if (!user) {
      const id = randomUUID();
      await pool.query(
        `INSERT INTO users (id, email, role, name, google_id, profile_picture, auth_provider)
         VALUES ($1, $2, 'faculty', $3, $4, $5, 'google')`,
        [id, email, name, googleId, picture || null]
      );
      ({ rows } = await pool.query('SELECT * FROM users WHERE id = $1', [id]));
      user = rows[0];
    } else {
      if (!user.is_active) return res.status(403).json({ error: 'Account is inactive' });
      if (!user.google_id) {
        await pool.query(
          'UPDATE users SET google_id = $1, profile_picture = $2, auth_provider = $3 WHERE id = $4',
          [googleId, picture || null, 'google', user.id]
        );
        ({ rows } = await pool.query('SELECT * FROM users WHERE id = $1', [user.id]));
        user = rows[0];
      }
    }

    res.json({ success: true, token: makeToken(user), user: safeUser(user) });
  } catch (error) {
    console.error('Google auth error:', error);
    if (error.message?.includes('Token used too late')) {
      return res.status(401).json({ error: 'Google token expired. Please try again.' });
    }
    res.status(500).json({ error: 'Google authentication failed' });
  }
});

module.exports = router;
