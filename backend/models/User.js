const mongoose = require('mongoose');

const userSchema = new mongoose.Schema({
  email: {
    type: String,
    required: true,
    unique: true,
    lowercase: true,
    trim: true
  },
  password: {
    type: String,
    required: false  // Not required for Google auth users
  },
  role: {
    type: String,
    required: true,
    enum: ['instructor', 'student', 'faculty', 'hod', 'principal']
  },
  name: {
    type: String,
    required: true
  },
  rollNumber: {
    type: String,
    sparse: true,
    unique: true
  },
  department: String,
  phone: String,
  isActive: {
    type: Boolean,
    default: true
  },
  // Class Teacher assignment (applicable only if role is faculty/instructor)
  assignedClass: {
    isClassTeacher: {
      type: Boolean,
      default: false
    },
    year: String,
    section: String
  },
  // Google Auth fields
  authProvider: {
    type: String,
    enum: ['local', 'google'],
    default: 'local'
  },
  googleId: {
    type: String,
    sparse: true,
    unique: true
  },
  profilePicture: String
}, { timestamps: true });

userSchema.index({ email: 1 });
userSchema.index({ role: 1 });
userSchema.index({ googleId: 1 });

module.exports = mongoose.model('User', userSchema);
