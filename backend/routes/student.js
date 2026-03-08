const express = require('express');
const router = express.Router();
const Session = require('../models/Session');
const Attendance = require('../models/Attendance');
const { authMiddleware, requireRole } = require('../middleware/auth');
const { verifyQRToken } = require('../services/qrService');
const axios = require('axios');

const FACE_SERVICE_URL = process.env.FACE_SERVICE_URL || 'http://localhost:5001';

// Mark attendance
router.post('/attendance/mark', authMiddleware, requireRole('student'), async (req, res) => {
  try {
    const { qrToken, faceImage } = req.body;

    // 1. Check qrToken exists
    if (!qrToken) {
      return res.status(400).json({ error: 'QR token is required' });
    }

    // 2. Check faceImage exists
    if (!faceImage) {
      return res.status(400).json({ error: 'Face image is required' });
    }

    // 3. Call Flask face verification service
    let faceVerificationResult;
    try {
      const response = await axios.post(`${FACE_SERVICE_URL}/face/verify`, {
        studentId: req.user.id,
        faceImage: faceImage
      });
      faceVerificationResult = response.data;
    } catch (error) {
      console.error('Face verification service error:', error.message);
      return res.status(503).json({ error: 'Face verification service unavailable' });
    }

    // 4. If verified = false → reject
    if (!faceVerificationResult.verified) {
      return res.status(400).json({ 
        error: 'Face verification failed',
        confidence: faceVerificationResult.confidence
      });
    }

    // 5. If verified = true → continue existing QR validation
    // 6. Verify QR signature
    const qrVerification = verifyQRToken(qrToken);
    if (!qrVerification.valid) {
      return res.status(400).json({ error: qrVerification.error });
    }

    const { sessionId } = qrVerification.data;

    // 7. Find session
    const session = await Session.findById(sessionId);
    if (!session) {
      return res.status(404).json({ error: 'Session not found' });
    }

    // 8. Session must be active
    if (session.status !== 'active') {
      return res.status(400).json({ error: 'Session is not active' });
    }

    // 9. Scanned QR must match session.currentQRToken
    if (session.currentQRToken !== qrToken) {
      return res.status(400).json({ error: 'QR code is outdated. Please scan the latest QR code.' });
    }

    // 10. Session.qrExpiresAt must still be valid
    if (!session.qrExpiresAt || session.qrExpiresAt < new Date()) {
      return res.status(400).json({ error: 'QR code has expired' });
    }

    // 11. Duplicate attendance must fail
    const existingAttendance = await Attendance.findOne({
      sessionId: session._id,
      studentId: req.user.id
    });

    if (existingAttendance) {
      return res.status(400).json({ error: 'Attendance already marked for this session' });
    }

    // 12. Create attendance
    const attendance = new Attendance({
      sessionId: session._id,
      studentId: req.user.id,
      markedAt: new Date(),
      faceVerified: true,
      qrVerified: true
    });

    await attendance.save();

    // 13. Increment presentCount
    session.presentCount += 1;
    await session.save();

    res.status(201).json({
      message: 'Attendance marked successfully',
      attendance: {
        sessionId: attendance.sessionId,
        markedAt: attendance.markedAt,
        className: session.className,
        subject: session.subject
      },
      faceConfidence: faceVerificationResult.confidence
    });
  } catch (error) {
    console.error('Mark attendance error:', error);
    res.status(500).json({ error: 'Failed to mark attendance' });
  }
});

// Get attendance history for student
router.get('/attendance/history', authMiddleware, requireRole('student'), async (req, res) => {
  try {
    const attendanceRecords = await Attendance.find({ studentId: req.user.id })
      .populate('sessionId', 'className subject startTime')
      .sort({ markedAt: -1 })
      .limit(50);

    res.json({
      attendance: attendanceRecords.map(a => ({
        id: a._id,
        className: a.sessionId?.className,
        subject: a.sessionId?.subject,
        markedAt: a.markedAt,
        sessionDate: a.sessionId?.startTime,
        faceVerified: a.faceVerified,
        qrVerified: a.qrVerified
      }))
    });
  } catch (error) {
    console.error('Get attendance history error:', error);
    res.status(500).json({ error: 'Failed to fetch attendance history' });
  }
});

module.exports = router;
