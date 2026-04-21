/**
 * Seed PostgreSQL users table from faculty_assignments.json + student CSVs.
 * Run once: node scripts/seed.js
 * Safe to re-run — uses INSERT ... ON CONFLICT DO NOTHING.
 */
require('dotenv').config({ path: require('path').join(__dirname, '..', '.env') });
const pool = require('../config/db');
const bcrypt = require('bcryptjs');
const { randomUUID } = require('crypto');
const fs = require('fs');
const path = require('path');
const csv = require('csv-parser');

const FACULTY_JSON = path.join(__dirname, '../../frontend-instructor/faculty_assignments.json');
const STUDENTS_CSE = path.join(__dirname, '../students_csv/students_cse.csv');
const STUDENTS_ECE = path.join(__dirname, '../students_csv/students_ece.csv');

async function readCSV(filePath) {
  return new Promise((resolve, reject) => {
    const rows = [];
    fs.createReadStream(filePath)
      .pipe(csv())
      .on('data', row => rows.push(row))
      .on('end', () => resolve(rows))
      .on('error', reject);
  });
}

async function main() {
  // Wait a moment for pool to init
  await new Promise(r => setTimeout(r, 1000));

  const insert = async (id, email, password, role, name, rollNumber, department) => {
    await pool.query(
      `INSERT INTO users (id, email, password, role, name, roll_number, department)
       VALUES ($1, $2, $3, $4, $5, $6, $7)
       ON CONFLICT (email) DO NOTHING`,
      [id, email, password, role, name, rollNumber || null, department || null]
    );
  };

  // 1. Principal admin
  const adminPass = await bcrypt.hash('Admin@1234', 10);
  await insert(randomUUID(), 'admin@bvrithyderabad.edu.in', adminPass, 'principal', 'Admin Principal', null, null);
  console.log('✓ Principal: admin@bvrithyderabad.edu.in / Admin@1234');

  // 2. Faculty
  const facultyData = JSON.parse(fs.readFileSync(FACULTY_JSON, 'utf8'));
  const facultyMap = facultyData.faculty;
  const facPass = await bcrypt.hash('Faculty@1234', 10);
  let count = 0;
  for (const [, info] of Object.entries(facultyMap)) {
    const dept = info.assignments?.[0]?.department || 'CSE';
    const email = `${info.id.replace(/_/g, '.')}@bvrithyderabad.edu.in`;
    await insert(randomUUID(), email, facPass, 'faculty', info.display_name, null, dept);
    count++;
  }
  console.log(`✓ ${count} faculty accounts (default: Faculty@1234)`);

  // 3. Students
  let studentCount = 0;
  for (const { file, dept } of [
    { file: STUDENTS_CSE, dept: 'CSE' },
    { file: STUDENTS_ECE, dept: 'ECE' }
  ]) {
    const rows = await readCSV(file);
    const stuPass = await bcrypt.hash('Student@1234', 10);
    for (const row of rows) {
      const rn = (row.rollnumber || row.roll_number || '').trim();
      const email = (row.email || '').trim();
      const name = (row.name || '').trim();
      if (!rn || !email) continue;
      await insert(randomUUID(), email, stuPass, 'student', name, rn, dept);
      studentCount++;
    }
  }
  console.log(`✓ ${studentCount} student accounts (default: Student@1234)`);

  await pool.end();
  console.log('\nDone.');
}

main().catch(err => { console.error(err); process.exit(1); });
