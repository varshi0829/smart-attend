const mongoose = require('mongoose');

const faceDataSchema = new mongoose.Schema({
  studentId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true,
    unique: true
  },
  embeddings: {
    type: [[Number]],
    required: true
  },
  imageCount: {
    type: Number,
    required: true
  }
}, { timestamps: true });

faceDataSchema.index({ studentId: 1 });

module.exports = mongoose.model('FaceData', faceDataSchema);
