const mongoose = require('mongoose');

const sessionSchema = new mongoose.Schema({
  instructorId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  className: {
    type: String,
    required: true
  },
  subject: String,
  department: String,
  status: {
    type: String,
    required: true,
    enum: ['active', 'stopped'],
    default: 'active'
  },
  startTime: {
    type: Date,
    required: true
  },
  stopTime: Date,
  currentQRToken: String,
  qrExpiresAt: Date,
  presentCount: {
    type: Number,
    default: 0
  }
}, { timestamps: true });

sessionSchema.index({ instructorId: 1, createdAt: -1 });
sessionSchema.index({ status: 1 });

module.exports = mongoose.model('Session', sessionSchema);
