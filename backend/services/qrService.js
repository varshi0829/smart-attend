const jwt = require('jsonwebtoken');
const QRCode = require('qrcode');

const QR_SECRET = process.env.JWT_SECRET + '_qr';
const QR_TTL_SECONDS = 45;

function generateQRToken(sessionId, instructorId) {
  return jwt.sign(
    { sessionId, instructorId, type: 'qr' },
    QR_SECRET,
    { expiresIn: QR_TTL_SECONDS }
  );
}

function verifyQRToken(token) {
  try {
    const data = jwt.verify(token, QR_SECRET);
    if (data.type !== 'qr') return { valid: false, error: 'Invalid QR token type' };
    return { valid: true, data };
  } catch (err) {
    if (err.name === 'TokenExpiredError') return { valid: false, error: 'QR code has expired' };
    return { valid: false, error: 'Invalid QR code' };
  }
}

async function generateQRImage(token) {
  return QRCode.toDataURL(token, { width: 300, margin: 2 });
}

module.exports = { generateQRToken, verifyQRToken, generateQRImage };
