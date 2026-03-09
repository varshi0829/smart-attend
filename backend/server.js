require('dotenv').config();
const express = require('express');
const cors = require('cors');
const https = require('https');
const fs = require('fs');
const connectDB = require('./config/db');

const app = express();

// Middleware
app.use(cors());
app.use(express.json({ limit: '10mb' }));

// Connect to MongoDB
connectDB();

// Routes
app.use('/api/auth', require('./routes/auth'));
app.use('/api/instructor', require('./routes/instructor'));
app.use('/api/student', require('./routes/student'));

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', message: 'Server is running' });
});

// Error handling
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Something went wrong!' });
});

const PORT = process.env.PORT || 5000;

// Use HTTPS if certificates exist, fallback to HTTP
if (fs.existsSync('./server.key') && fs.existsSync('./server.cert')) {
  const options = {
    key: fs.readFileSync('./server.key'),
    cert: fs.readFileSync('./server.cert')
  };
  https.createServer(options, app).listen(PORT, '0.0.0.0', () => {
    console.log(`✓ HTTPS Server running on https://YOUR_IP:${PORT}`);
  });
} else {
  app.listen(PORT, '0.0.0.0', () => {
    console.log(`✓ HTTP Server running on port ${PORT}`);
    console.log(`  Run: openssl req -nodes -new -x509 -keyout server.key -out server.cert`);
    console.log(`  Then restart to enable HTTPS`);
  });
}