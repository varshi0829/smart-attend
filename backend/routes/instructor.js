const express = require('express');
const router = express.Router();
const Session = require('../models/Session');
const Attendance = require('../models/Attendance');
const User = require('../models/User');
const { authMiddleware, requireRole } = require('../middleware/auth');
const { generateQRToken, generateQRImage } = require('../services/qrService');
const { buildSessionFilter, canAccessDepartment } = require('../utils/roleUtils');

// ── Role constants ──────────────────────────────────────────────────────────
const SESSION_ROLES = ['instructor', 'faculty', 'hod', 'principal'];

// ── Start session ────────────────────────────────────────────────────────────
router.post('/session/start', authMiddleware, requireRole('instructor', 'faculty', 'hod'), async (req, res) => {
  try {
    const { className, subject, department, year, section } = req.body;

    if (!className) return res.status(400).json({ error: 'Class name is required' });

    const activeSession = await Session.findOne({ instructorId: req.user.id, status: 'active' });
    if (activeSession) return res.status(400).json({ error: 'You already have an active session. Stop it first.' });

    const session = new Session({
      instructorId: req.user.id,
      className,
      subject,
      department: department || req.user.department,
      year,
      section,
      status: 'active',
      startTime: new Date()
    });

    await session.save();

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
        department: session.department,
        year: session.year,
        section: session.section,
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

// ── Stop session ─────────────────────────────────────────────────────────────
router.post('/session/:id/stop', authMiddleware, requireRole(...SESSION_ROLES), async (req, res) => {
  try {
    let query = { _id: req.params.id };
    if (req.user.role === 'principal') { /* no extra filter */ }
    else if (req.user.role === 'hod')  { query.department = req.user.department; }
    else                               { query.instructorId = req.user.id; }

    const session = await Session.findOne(query);
    if (!session) return res.status(404).json({ error: 'Session not found' });
    if (session.status === 'stopped') return res.status(400).json({ error: 'Session already stopped' });

    session.status = 'stopped';
    session.stopTime = new Date();
    session.currentQRToken = null;
    session.qrExpiresAt = null;
    await session.save();

    res.json({
      message: 'Session stopped successfully',
      session: { id: session._id, className: session.className, status: session.status, stopTime: session.stopTime, presentCount: session.presentCount }
    });
  } catch (error) {
    console.error('Stop session error:', error);
    res.status(500).json({ error: 'Failed to stop session' });
  }
});

// ── Get session details ──────────────────────────────────────────────────────
router.get('/session/:id', authMiddleware, requireRole(...SESSION_ROLES), async (req, res) => {
  try {
    const filter = { ...buildSessionFilter(req.user), _id: req.params.id };
    const session = await Session.findOne(filter).populate('instructorId', 'name email role department');

    if (!session) return res.status(404).json({ error: 'Session not found or access denied' });

    const attendanceList = await Attendance.find({ sessionId: session._id })
      .populate('studentId', 'name email rollNumber')
      .sort({ markedAt: -1 });

    res.json({
      session: {
        id: session._id, className: session.className, subject: session.subject,
        department: session.department, year: session.year, section: session.section,
        status: session.status, startTime: session.startTime, stopTime: session.stopTime,
        presentCount: session.presentCount, instructor: session.instructorId
      },
      attendance: attendanceList.map(a => ({
        student: a.studentId, markedAt: a.markedAt,
        faceVerified: a.faceVerified, qrVerified: a.qrVerified, confidence: a.confidence
      }))
    });
  } catch (error) {
    console.error('Get session error:', error);
    res.status(500).json({ error: 'Failed to fetch session' });
  }
});

// ── Get QR for active session ────────────────────────────────────────────────
router.get('/session/:id/qr', authMiddleware, requireRole(...SESSION_ROLES), async (req, res) => {
  try {
    const session = await Session.findOne({ _id: req.params.id, instructorId: req.user.id });
    if (!session) return res.status(404).json({ error: 'Session not found' });
    if (session.status !== 'active') return res.status(400).json({ error: 'Session is not active' });

    if (!session.currentQRToken || !session.qrExpiresAt || session.qrExpiresAt < new Date()) {
      session.currentQRToken = generateQRToken(session._id.toString(), req.user.id);
      session.qrExpiresAt = new Date(Date.now() + 45000);
      await session.save();
    }

    const qrImage = await generateQRImage(session.currentQRToken);
    res.json({ qrToken: session.currentQRToken, qrImage, expiresAt: session.qrExpiresAt });
  } catch (error) {
    console.error('Get QR error:', error);
    res.status(500).json({ error: 'Failed to generate QR code' });
  }
});

// ── List sessions (role-filtered) ────────────────────────────────────────────
router.get('/sessions', authMiddleware, requireRole(...SESSION_ROLES), async (req, res) => {
  try {
    const filter = buildSessionFilter(req.user);
    const sessions = await Session.find(filter)
      .populate('instructorId', 'name email department')
      .sort({ createdAt: -1 })
      .limit(100);

    res.json({
      sessions: sessions.map(s => ({
        id: s._id, className: s.className, subject: s.subject,
        department: s.department, year: s.year, section: s.section,
        status: s.status, startTime: s.startTime, stopTime: s.stopTime,
        presentCount: s.presentCount, instructor: s.instructorId
      }))
    });
  } catch (error) {
    console.error('Get sessions error:', error);
    res.status(500).json({ error: 'Failed to fetch sessions' });
  }
});

// ── HOD: Department summary ──────────────────────────────────────────────────
router.get('/department-summary', authMiddleware, requireRole('hod', 'principal'), async (req, res) => {
  try {
    const dept = req.user.role === 'hod' ? req.user.department : req.query.department;
    if (!dept) return res.status(400).json({ error: 'Department is required' });

    const today = new Date(); today.setHours(0, 0, 0, 0);

    const [totalSessions, todaySessions, activeSessions, facultyCount] = await Promise.all([
      Session.countDocuments({ department: dept }),
      Session.countDocuments({ department: dept, startTime: { $gte: today } }),
      Session.countDocuments({ department: dept, status: 'active' }),
      User.countDocuments({ department: dept, role: { $in: ['faculty', 'instructor', 'hod'] } })
    ]);

    const presentToday = await Attendance.aggregate([
      { $lookup: { from: 'sessions', localField: 'sessionId', foreignField: '_id', as: 'session' } },
      { $unwind: '$session' },
      { $match: { 'session.department': dept, 'session.startTime': { $gte: today } } },
      { $count: 'total' }
    ]);

    const recentSessions = await Session.find({ department: dept })
      .populate('instructorId', 'name email')
      .sort({ createdAt: -1 })
      .limit(20);

    res.json({
      department: dept,
      stats: { totalSessions, todaySessions, activeSessions, facultyCount, presentToday: presentToday[0]?.total || 0 },
      recentSessions: recentSessions.map(s => ({
        id: s._id, className: s.className, subject: s.subject,
        year: s.year, section: s.section, status: s.status,
        startTime: s.startTime, presentCount: s.presentCount, instructor: s.instructorId
      }))
    });
  } catch (error) {
    console.error('Department summary error:', error);
    res.status(500).json({ error: 'Failed to fetch department summary' });
  }
});

// ── Principal: Institution overview ─────────────────────────────────────────
router.get('/institution-overview', authMiddleware, requireRole('principal'), async (req, res) => {
  try {
    const today = new Date(); today.setHours(0, 0, 0, 0);

    const [totalSessions, todaySessions, activeSessions, totalFaculty, totalStudents] = await Promise.all([
      Session.countDocuments({}),
      Session.countDocuments({ startTime: { $gte: today } }),
      Session.countDocuments({ status: 'active' }),
      User.countDocuments({ role: { $in: ['faculty', 'instructor', 'hod'] } }),
      User.countDocuments({ role: 'student' })
    ]);

    const deptBreakdown = await Session.aggregate([
      {
        $group: {
          _id: '$department',
          sessionCount: { $sum: 1 },
          todayCount: { $sum: { $cond: [{ $gte: ['$startTime', today] }, 1, 0] } },
          activeCount: { $sum: { $cond: [{ $eq: ['$status', 'active'] }, 1, 0] } },
          totalPresent: { $sum: '$presentCount' }
        }
      },
      { $sort: { sessionCount: -1 } }
    ]);

    const recentSessions = await Session.find({})
      .populate('instructorId', 'name department')
      .sort({ createdAt: -1 })
      .limit(20);

    res.json({
      stats: { totalSessions, todaySessions, activeSessions, totalFaculty, totalStudents },
      departmentBreakdown: deptBreakdown,
      recentSessions: recentSessions.map(s => ({
        id: s._id, className: s.className, subject: s.subject,
        department: s.department, year: s.year, section: s.section,
        status: s.status, startTime: s.startTime,
        presentCount: s.presentCount, instructor: s.instructorId
      }))
    });
  } catch (error) {
    console.error('Institution overview error:', error);
    res.status(500).json({ error: 'Failed to fetch institution overview' });
  }
});

// ── Faculty list (HOD / Principal) ──────────────────────────────────────────
router.get('/faculty', authMiddleware, requireRole('hod', 'principal'), async (req, res) => {
  try {
    const filter = { role: { $in: ['faculty', 'instructor', 'hod'] }, isActive: true };
    if (req.user.role === 'hod') filter.department = req.user.department;

    const faculty = await User.find(filter)
      .select('name email role department assignedClass')
      .sort({ name: 1 });

    res.json({
      faculty: faculty.map(f => ({
        id: f._id, name: f.name, email: f.email, role: f.role,
        department: f.department,
        isClassTeacher: f.assignedClass?.isClassTeacher || false,
        assignedClass: f.assignedClass
      }))
    });
  } catch (error) {
    console.error('Faculty list error:', error);
    res.status(500).json({ error: 'Failed to fetch faculty list' });
  }
});

module.exports = router;
