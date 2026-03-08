const mongoose = require('mongoose');

const attendanceSchema = new mongoose.Schema({
  sessionId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'Session',
    required: true
  },
  studentId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  markedAt: {
    type: Date,
    required: true,
    default: Date.now
  },
  faceVerified: {
    type: Boolean,
    required: true
  },
  qrVerified: {
    type: Boolean,
    required: true
  },
  confidence: Number
}, { timestamps: true });

// Prevent duplicate attendance - one student can mark only once per session
attendanceSchema.index({ sessionId: 1, studentId: 1 }, { unique: true });
attendanceSchema.index({ studentId: 1, createdAt: -1 });

module.exports = mongoose.model('Attendance', attendanceSchema);
