const express = require('express');
const axios = require('axios');
const pool = require('../config/db');
const { authMiddleware, requireRole } = require('../middleware/auth');
const { verifyQRToken } = require('../services/qrService');

const router = express.Router();
const FACE_SERVICE_URL = process.env.FACE_SERVICE_URL || 'http://localhost:5001';

// Mark attendance
router.post('/attendance/mark', authMiddleware, requireRole('student'), async (req, res) => {
  try {
    const { qrToken, faceImage } = req.body;
    if (!qrToken) return res.status(400).json({ error: 'QR token is required' });
    if (!faceImage) return res.status(400).json({ error: 'Face image is required' });

    // Face verification
    let faceResult;
    try {
      const response = await axios.post(`${FACE_SERVICE_URL}/face/verify`, {
        studentId: req.user.id,
        faceImage
      });
      faceResult = response.data;
    } catch {
      return res.status(503).json({ error: 'Face verification service unavailable' });
    }

    if (!faceResult.verified) {
      return res.status(400).json({ error: 'Face verification failed', confidence: faceResult.confidence });
    }

    // QR verification
    const qrCheck = verifyQRToken(qrToken);
    if (!qrCheck.valid) return res.status(400).json({ error: qrCheck.error });

    const { sessionId } = qrCheck.data;
    const { rows: sessRows } = await pool.query('SELECT * FROM sessions WHERE session_id = $1', [sessionId]);
    const session = sessRows[0];
    if (!session) return res.status(404).json({ error: 'Session not found' });
    if (session.status !== 'active') return res.status(400).json({ error: 'Session is not active' });
    if (session.current_qr_token !== qrToken) {
      return res.status(400).json({ error: 'QR code is outdated. Please scan the latest QR code.' });
    }
    if (!session.qr_expires_at || new Date(session.qr_expires_at) < new Date()) {
      return res.status(400).json({ error: 'QR code has expired' });
    }

    // Look up student roll_number
    const { rows: userRows } = await pool.query('SELECT roll_number FROM users WHERE id = $1', [req.user.id]);
    const rollNumber = userRows[0]?.roll_number;
    if (!rollNumber) return res.status(400).json({ error: 'Student roll number not found' });

    // Duplicate check
    const dup = await pool.query(
      'SELECT 1 FROM attendance WHERE session_id = $1 AND roll_number = $2',
      [sessionId, rollNumber]
    );
    if (dup.rows[0]) return res.status(400).json({ error: 'Attendance already marked for this session' });

    // Record attendance
    await pool.query(
      `INSERT INTO attendance (roll_number, session_id, timestamp, confidence, face_verified, qr_verified)
       VALUES ($1, $2, NOW(), $3, TRUE, TRUE)`,
      [rollNumber, sessionId, faceResult.confidence || null]
    );

    await pool.query(
      'UPDATE sessions SET present_count = present_count + 1 WHERE session_id = $1',
      [sessionId]
    );

    res.status(201).json({
      message: 'Attendance marked successfully',
      attendance: { sessionId, markedAt: new Date(), className: session.class_name, subject: session.subject },
      faceConfidence: faceResult.confidence
    });
  } catch (error) {
    console.error('Mark attendance error:', error);
    res.status(500).json({ error: 'Failed to mark attendance' });
  }
});

// Attendance history
router.get('/attendance/history', authMiddleware, requireRole('student'), async (req, res) => {
  try {
    const { rows: userRows } = await pool.query('SELECT roll_number FROM users WHERE id = $1', [req.user.id]);
    const rollNumber = userRows[0]?.roll_number;
    if (!rollNumber) return res.json({ attendance: [] });

    const { rows } = await pool.query(
      `SELECT a.*, s.class_name, s.subject, s.start_time
       FROM attendance a LEFT JOIN sessions s ON a.session_id = s.session_id
       WHERE a.roll_number = $1 ORDER BY a.timestamp DESC LIMIT 50`,
      [rollNumber]
    );

    res.json({
      attendance: rows.map(a => ({
        className: a.class_name,
        subject: a.subject,
        markedAt: a.timestamp,
        sessionDate: a.start_time,
        faceVerified: a.face_verified,
        qrVerified: a.qr_verified
      }))
    });
  } catch (error) {
    console.error('Get attendance history error:', error);
    res.status(500).json({ error: 'Failed to fetch attendance history' });
  }
});

module.exports = router;
