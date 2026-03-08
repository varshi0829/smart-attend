const jwt = require('jsonwebtoken');
const QRCode = require('qrcode');
const crypto = require('crypto');

// Generate QR token with JWT
const generateQRToken = (sessionId, instructorId) => {
  const payload = {
    sessionId,
    instructorId,
    timestamp: Date.now(),
    expiresAt: Date.now() + 45000, // 45 seconds
    nonce: crypto.randomBytes(16).toString('hex')
  };

  return jwt.sign(payload, process.env.JWT_SECRET, { expiresIn: '45s' });
};

// Verify QR token
const verifyQRToken = (token) => {
  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    
    // Check if token is expired
    if (decoded.expiresAt < Date.now()) {
      return { valid: false, error: 'QR token expired' };
    }
    
    return { valid: true, data: decoded };
  } catch (error) {
    if (error.name === 'TokenExpiredError') {
      return { valid: false, error: 'QR token expired' };
    }
    return { valid: false, error: 'Invalid QR token' };
  }
};

// Generate QR code image
const generateQRImage = async (token) => {
  try {
    const qrDataURL = await QRCode.toDataURL(token, {
      errorCorrectionLevel: 'M',
      width: 300,
      margin: 2
    });
    return qrDataURL;
  } catch (error) {
    throw new Error('Failed to generate QR code image');
  }
};

module.exports = {
  generateQRToken,
  verifyQRToken,
  generateQRImage
};
