const express = require('express');
const { randomUUID } = require('crypto');
const pool = require('../config/db');
const { authMiddleware, requireRole } = require('../middleware/auth');
const { generateQRToken, generateQRImage } = require('../services/qrService');
const { buildSessionFilter } = require('../utils/roleUtils');

const router = express.Router();
const ALLOWED = ['instructor', 'faculty', 'hod', 'principal'];

// Start session
router.post('/session/start', authMiddleware, requireRole(...ALLOWED), async (req, res) => {
  try {
    const { className, subject, year, section } = req.body;
    if (!className) return res.status(400).json({ error: 'Class name is required' });

    const active = await pool.query(
      "SELECT session_id FROM sessions WHERE teacher_id = $1 AND status = 'active'",
      [req.user.id]
    );
    if (active.rows[0]) {
      return res.status(400).json({ error: 'You already have an active session. Please stop it first.' });
    }

    const id = randomUUID();
    const qrToken = generateQRToken(id, req.user.id);
    const qrExpiresAt = new Date(Date.now() + 45000);

    await pool.query(
      `INSERT INTO sessions (session_id, teacher_id, class_name, subject, department, year, section, status, start_time, current_qr_token, qr_expires_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, 'active', NOW(), $8, $9)`,
      [id, req.user.id, className, subject || null, req.user.department || null, year || null, section || null, qrToken, qrExpiresAt]
    );

    res.status(201).json({
      message: 'Session started successfully',
      session: { id, className, subject, status: 'active', startTime: new Date(), qrToken }
    });
  } catch (error) {
    console.error('Start session error:', error);
    res.status(500).json({ error: 'Failed to start session' });
  }
});

// Stop session
router.post('/session/:id/stop', authMiddleware, requireRole(...ALLOWED), async (req, res) => {
  try {
    const { rows } = await pool.query(
      'SELECT * FROM sessions WHERE session_id = $1 AND teacher_id = $2',
      [req.params.id, req.user.id]
    );
    const session = rows[0];
    if (!session) return res.status(404).json({ error: 'Session not found' });
    if (session.status === 'stopped') return res.status(400).json({ error: 'Session already stopped' });

    const { rows: updated } = await pool.query(
      "UPDATE sessions SET status = 'stopped', stop_time = NOW(), current_qr_token = NULL, qr_expires_at = NULL WHERE session_id = $1 RETURNING *",
      [session.session_id]
    );

    res.json({
      message: 'Session stopped successfully',
      session: {
        id: updated[0].session_id,
        className: updated[0].class_name,
        status: updated[0].status,
        stopTime: updated[0].stop_time,
        presentCount: updated[0].present_count
      }
    });
  } catch (error) {
    console.error('Stop session error:', error);
    res.status(500).json({ error: 'Failed to stop session' });
  }
});

// Get session details
router.get('/session/:id', authMiddleware, requireRole(...ALLOWED), async (req, res) => {
  try {
    let query, queryParams;
    if (req.user.role === 'principal') {
      query = 'SELECT s.*, u.name AS instructor_name, u.email AS instructor_email FROM sessions s LEFT JOIN users u ON s.teacher_id = u.id WHERE s.session_id = $1';
      queryParams = [req.params.id];
    } else if (req.user.role === 'hod') {
      query = 'SELECT s.*, u.name AS instructor_name, u.email AS instructor_email FROM sessions s LEFT JOIN users u ON s.teacher_id = u.id WHERE s.session_id = $1 AND s.department = $2';
      queryParams = [req.params.id, req.user.department];
    } else {
      query = 'SELECT s.*, u.name AS instructor_name, u.email AS instructor_email FROM sessions s LEFT JOIN users u ON s.teacher_id = u.id WHERE s.session_id = $1 AND s.teacher_id = $2';
      queryParams = [req.params.id, req.user.id];
    }

    const { rows } = await pool.query(query, queryParams);
    const session = rows[0];
    if (!session) return res.status(404).json({ error: 'Session not found' });

    const { rows: att } = await pool.query(
      `SELECT a.*, u.name AS student_name, u.email AS student_email, u.roll_number
       FROM attendance a LEFT JOIN users u ON a.roll_number = u.roll_number
       WHERE a.session_id = $1 ORDER BY a.timestamp DESC`,
      [session.session_id]
    );

    res.json({
      session: {
        id: session.session_id,
        className: session.class_name,
        subject: session.subject,
        status: session.status,
        startTime: session.start_time,
        stopTime: session.stop_time,
        presentCount: session.present_count,
        instructor: { name: session.instructor_name, email: session.instructor_email }
      },
      attendance: att.map(a => ({
        student: { rollNumber: a.roll_number, name: a.student_name, email: a.student_email },
        markedAt: a.timestamp,
        faceVerified: a.face_verified,
        qrVerified: a.qr_verified,
        confidence: a.confidence
      }))
    });
  } catch (error) {
    console.error('Get session error:', error);
    res.status(500).json({ error: 'Failed to fetch session' });
  }
});

// Get/refresh QR code
router.get('/session/:id/qr', authMiddleware, requireRole(...ALLOWED), async (req, res) => {
  try {
    const { rows } = await pool.query(
      'SELECT * FROM sessions WHERE session_id = $1 AND teacher_id = $2',
      [req.params.id, req.user.id]
    );
    const session = rows[0];
    if (!session) return res.status(404).json({ error: 'Session not found' });
    if (session.status !== 'active') return res.status(400).json({ error: 'Session is not active' });

    let { current_qr_token: qrToken, qr_expires_at: qrExpiresAt } = session;

    if (!qrToken || !qrExpiresAt || new Date(qrExpiresAt) < new Date()) {
      qrToken = generateQRToken(session.session_id, req.user.id);
      qrExpiresAt = new Date(Date.now() + 45000);
      await pool.query(
        'UPDATE sessions SET current_qr_token = $1, qr_expires_at = $2 WHERE session_id = $3',
        [qrToken, qrExpiresAt, session.session_id]
      );
    }

    const qrImage = await generateQRImage(qrToken);
    res.json({ qrToken, qrImage, expiresAt: qrExpiresAt });
  } catch (error) {
    console.error('Get QR error:', error);
    res.status(500).json({ error: 'Failed to generate QR code' });
  }
});

// List sessions (role-filtered)
router.get('/sessions', authMiddleware, requireRole(...ALLOWED), async (req, res) => {
  try {
    const { where, params } = buildSessionFilter(req.user);
    const { rows } = await pool.query(
      `SELECT s.*, u.name AS instructor_name FROM sessions s
       LEFT JOIN users u ON s.teacher_id = u.id
       WHERE ${where} ORDER BY s.start_time DESC LIMIT 100`,
      params
    );

    res.json({
      sessions: rows.map(s => ({
        id: s.session_id,
        className: s.class_name,
        subject: s.subject,
        status: s.status,
        startTime: s.start_time,
        stopTime: s.stop_time,
        presentCount: s.present_count,
        department: s.department,
        year: s.year,
        section: s.section,
        instructorName: s.instructor_name
      }))
    });
  } catch (error) {
    console.error('Get sessions error:', error);
    res.status(500).json({ error: 'Failed to fetch sessions' });
  }
});

module.exports = router;
