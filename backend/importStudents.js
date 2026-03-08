require('dotenv').config();
const fs = require('fs');
const csv = require('csv-parser');
const mongoose = require('mongoose');
const User = require('./models/User');

const COLLEGE_DOMAIN = '@bvrithyderabad.edu.in';

// Connect to MongoDB
mongoose.connect(process.env.MONGODB_URI)
  .then(() => console.log('✓ MongoDB connected'))
  .catch(err => {
    console.error('✗ MongoDB connection error:', err.message);
    process.exit(1);
  });

// Generate email from roll number if missing
function generateEmail(rollNumber) {
  return rollNumber.toLowerCase() + COLLEGE_DOMAIN;
}

// Import students from CSV
async function importStudents(csvFilePath) {
  const students = [];
  const stats = {
    total: 0,
    inserted: 0,
    updated: 0,
    skipped: 0,
    errors: []
  };

  return new Promise((resolve, reject) => {
    fs.createReadStream(csvFilePath)
      .pipe(csv())
      .on('data', (row) => {
        stats.total++;
        
        // Generate email if missing
        const email = row.email || generateEmail(row.rollNumber);
        
        students.push({
          rollNumber: row.rollNumber,
          name: row.name,
          email: email,
          department: row.department || 'CSE',
          role: 'student',
          authProvider: 'google',  // Students will use Google login
          isActive: true
        });
      })
      .on('end', async () => {
        console.log(`\n📊 Processing ${stats.total} students...\n`);

        // Bulk upsert operation
        for (const student of students) {
          try {
            const result = await User.findOneAndUpdate(
              { email: student.email },  // Find by email
              {
                $set: student,
                $setOnInsert: { createdAt: new Date() }
              },
              {
                upsert: true,
                new: true,
                setDefaultsOnInsert: true
              }
            );

            if (result.createdAt && new Date() - result.createdAt < 1000) {
              stats.inserted++;
              console.log(`✓ Inserted: ${student.rollNumber} - ${student.name}`);
            } else {
              stats.updated++;
              console.log(`↻ Updated: ${student.rollNumber} - ${student.name}`);
            }
          } catch (error) {
            stats.errors.push({
              rollNumber: student.rollNumber,
              error: error.message
            });
            console.error(`✗ Error: ${student.rollNumber} - ${error.message}`);
          }
        }

        // Print summary
        console.log('\n' + '='.repeat(50));
        console.log('📈 IMPORT SUMMARY');
        console.log('='.repeat(50));
        console.log(`Total rows processed: ${stats.total}`);
        console.log(`✓ Inserted: ${stats.inserted}`);
        console.log(`↻ Updated: ${stats.updated}`);
        console.log(`⊘ Skipped: ${stats.skipped}`);
        console.log(`✗ Errors: ${stats.errors.length}`);
        console.log('='.repeat(50) + '\n');

        if (stats.errors.length > 0) {
          console.log('❌ Errors:');
          stats.errors.forEach(err => {
            console.log(`  - ${err.rollNumber}: ${err.error}`);
          });
        }

        mongoose.connection.close();
        resolve(stats);
      })
      .on('error', (error) => {
        console.error('✗ CSV parsing error:', error.message);
        mongoose.connection.close();
        reject(error);
      });
  });
}

// Run import
const csvFile = process.argv[2] || './students.csv';

if (!fs.existsSync(csvFile)) {
  console.error(`✗ CSV file not found: ${csvFile}`);
  console.log('\nUsage: node importStudents.js <path-to-csv>');
  console.log('Example: node importStudents.js ./students.csv');
  process.exit(1);
}

console.log(`📂 Importing from: ${csvFile}\n`);
importStudents(csvFile)
  .then(() => {
    console.log('✅ Import completed successfully!');
    process.exit(0);
  })
  .catch((error) => {
    console.error('❌ Import failed:', error.message);
    process.exit(1);
  });
