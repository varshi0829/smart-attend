require('dotenv').config();
const express = require('express');
const cors = require('cors');

// Initialize DB pool (runs CREATE TABLE IF NOT EXISTS on startup)
require('./config/db');

const app = express();
app.use(cors());
app.use(express.json({ limit: '10mb' }));

app.use('/api/auth', require('./routes/auth'));
app.use('/api/instructor', require('./routes/instructor'));
app.use('/api/student', require('./routes/student'));

app.get('/health', (req, res) => res.json({ status: 'ok', message: 'Server is running' }));

app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Something went wrong!' });
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => console.log(`✓ Server running on port ${PORT}`));
