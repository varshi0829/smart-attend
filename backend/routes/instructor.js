const express = require('express');
const router = express.Router();
const Session = require('../models/Session');
const Attendance = require('../models/Attendance');
const { authMiddleware, requireRole } = require('../middleware/auth');
const { generateQRToken, generateQRImage } = require('../services/qrService');

// Start attendance session
router.post('/session/start', authMiddleware, requireRole('instructor'), async (req, res) => {
  try {
    const { className, subject } = req.body;

    if (!className) {
      return res.status(400).json({ error: 'Class name is required' });
    }

    // Check if instructor already has an active session
    const activeSession = await Session.findOne({
      instructorId: req.user.id,
      status: 'active'
    });

    if (activeSession) {
      return res.status(400).json({ error: 'You already have an active session. Please stop it first.' });
    }

    // Create session
    const session = new Session({
      instructorId: req.user.id,
      className,
      subject,
      status: 'active',
      startTime: new Date()
    });

    await session.save();

    // Generate initial QR token
    const qrToken = generateQRToken(session._id.toString(), req.user.id);
    session.currentQRToken = qrToken;
    session.qrExpiresAt = new Date(Date.now() + 45000);
    await session.save();

    res.status(201).json({
      message: 'Session started successfully',
      session: {
        id: session._id,
        className: session.className,
        subject: session.subject,
        status: session.status,
        startTime: session.startTime,
        qrToken
      }
    });
  } catch (error) {
    console.error('Start session error:', error);
    res.status(500).json({ error: 'Failed to start session' });
  }
});

// Stop attendance session
router.post('/session/:id/stop', authMiddleware, requireRole('instructor'), async (req, res) => {
  try {
    const session = await Session.findOne({
      _id: req.params.id,
      instructorId: req.user.id
    });

    if (!session) {
      return res.status(404).json({ error: 'Session not found' });
    }

    if (session.status === 'stopped') {
      return res.status(400).json({ error: 'Session already stopped' });
    }

    // Stop session and invalidate QR
    session.status = 'stopped';
    session.stopTime = new Date();
    session.currentQRToken = null;
    session.qrExpiresAt = null;
    await session.save();

    res.json({
      message: 'Session stopped successfully',
      session: {
        id: session._id,
        className: session.className,
        status: session.status,
        stopTime: session.stopTime,
        presentCount: session.presentCount
      }
    });
  } catch (error) {
    console.error('Stop session error:', error);
    res.status(500).json({ error: 'Failed to stop session' });
  }
});

// Get session details
router.get('/session/:id', authMiddleware, requireRole('instructor'), async (req, res) => {
  try {
    const session = await Session.findOne({
      _id: req.params.id,
      instructorId: req.user.id
    }).populate('instructorId', 'name email');

    if (!session) {
      return res.status(404).json({ error: 'Session not found' });
    }

    // Get attendance list
    const attendanceList = await Attendance.find({ sessionId: session._id })
      .populate('studentId', 'name email rollNumber')
      .sort({ markedAt: -1 });

    res.json({
      session: {
        id: session._id,
        className: session.className,
        subject: session.subject,
        status: session.status,
        startTime: session.startTime,
        stopTime: session.stopTime,
        presentCount: session.presentCount,
        instructor: session.instructorId
      },
      attendance: attendanceList.map(a => ({
        student: a.studentId,
        markedAt: a.markedAt,
        faceVerified: a.faceVerified,
        qrVerified: a.qrVerified
      }))
    });
  } catch (error) {
    console.error('Get session error:', error);
    res.status(500).json({ error: 'Failed to fetch session' });
  }
});

// Get current QR code
router.get('/session/:id/qr', authMiddleware, requireRole('instructor'), async (req, res) => {
  try {
    const session = await Session.findOne({
      _id: req.params.id,
      instructorId: req.user.id
    });

    if (!session) {
      return res.status(404).json({ error: 'Session not found' });
    }

    if (session.status !== 'active') {
      return res.status(400).json({ error: 'Session is not active' });
    }

    // Check if QR expired, generate new one
    if (!session.currentQRToken || !session.qrExpiresAt || session.qrExpiresAt < new Date()) {
      const qrToken = generateQRToken(session._id.toString(), req.user.id);
      session.currentQRToken = qrToken;
      session.qrExpiresAt = new Date(Date.now() + 45000);
      await session.save();
    }

    const qrImage = await generateQRImage(session.currentQRToken);

    res.json({
      qrToken: session.currentQRToken,
      qrImage,
      expiresAt: session.qrExpiresAt
    });
  } catch (error) {
    console.error('Get QR error:', error);
    res.status(500).json({ error: 'Failed to generate QR code' });
  }
});

// Get all sessions for instructor
router.get('/sessions', authMiddleware, requireRole('instructor'), async (req, res) => {
  try {
    const sessions = await Session.find({ instructorId: req.user.id })
      .sort({ createdAt: -1 })
      .limit(50);

    res.json({
      sessions: sessions.map(s => ({
        id: s._id,
        className: s.className,
        subject: s.subject,
        status: s.status,
        startTime: s.startTime,
        stopTime: s.stopTime,
        presentCount: s.presentCount
      }))
    });
  } catch (error) {
    console.error('Get sessions error:', error);
    res.status(500).json({ error: 'Failed to fetch sessions' });
  }
});

module.exports = router;
