const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://cse:cse@localhost:5432/smartattend_db'
});

async function initDB() {
  const client = await pool.connect();
  try {
    await client.query(`
      CREATE TABLE IF NOT EXISTS users (
        id              TEXT PRIMARY KEY,
        email           TEXT UNIQUE NOT NULL,
        password        TEXT,
        role            TEXT NOT NULL DEFAULT 'faculty',
        name            TEXT NOT NULL,
        roll_number     TEXT UNIQUE,
        department      TEXT,
        phone           TEXT,
        is_active       BOOLEAN NOT NULL DEFAULT TRUE,
        is_class_teacher BOOLEAN NOT NULL DEFAULT FALSE,
        assigned_year   TEXT,
        assigned_section TEXT,
        auth_provider   TEXT NOT NULL DEFAULT 'local',
        google_id       TEXT UNIQUE,
        profile_picture TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
      );

      CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
      CREATE INDEX IF NOT EXISTS idx_users_role  ON users(role);
      CREATE INDEX IF NOT EXISTS idx_users_dept  ON users(department);
    `);

    // Extend existing sessions table with Node-specific columns
    const sessionCols = [
      'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS class_name TEXT',
      'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS stop_time TIMESTAMPTZ',
      'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS current_qr_token TEXT',
      'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS qr_expires_at TIMESTAMPTZ',
      'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS present_count INTEGER NOT NULL DEFAULT 0',
    ];
    for (const sql of sessionCols) {
      await client.query(sql).catch(() => {}); // table may not exist yet; skip
    }

    // Extend existing attendance table
    const attCols = [
      'ALTER TABLE attendance ADD COLUMN IF NOT EXISTS face_verified BOOLEAN NOT NULL DEFAULT FALSE',
      'ALTER TABLE attendance ADD COLUMN IF NOT EXISTS qr_verified   BOOLEAN NOT NULL DEFAULT FALSE',
    ];
    for (const sql of attCols) {
      await client.query(sql).catch(() => {});
    }

    console.log('✓ PostgreSQL connected:', process.env.DATABASE_URL || 'postgresql://cse:cse@localhost:5432/smartattend_db');
  } finally {
    client.release();
  }
}

initDB().catch(err => {
  console.error('DB init error:', err.message);
  process.exit(1);
});

module.exports = pool;
