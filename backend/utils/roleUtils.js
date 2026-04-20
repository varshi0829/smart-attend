const User = require('../models/User');

/**
 * Fetch a user's role from the database by their ID.
 * Use this when you need a fresh DB-verified role (e.g., admin actions),
 * not for request-level checks (use req.user.role from JWT instead).
 *
 * @param {string} teacherId - MongoDB ObjectId string
 * @returns {{ role, department, assignedClass } | null}
 */
async function getUserRole(teacherId) {
  const user = await User.findById(teacherId)
    .select('role department assignedClass')
    .lean();
  if (!user) return null;
  return { role: user.role, department: user.department, assignedClass: user.assignedClass };
}

/**
 * Build a MongoDB filter for Session queries based on the caller's role.
 *
 * principal  → all sessions (no filter)
 * hod        → sessions in their department
 * faculty/instructor with isClassTeacher → own sessions + assigned class sessions
 * faculty/instructor (regular) → only own sessions
 *
 * @param {{ id, role, department, assignedClass }} user  - from req.user (JWT payload)
 * @returns {object} Mongoose filter object
 */
function buildSessionFilter(user) {
  const { role, department, assignedClass } = user;

  if (role === 'principal') return {};

  if (role === 'hod') return { department };

  if (assignedClass?.isClassTeacher) {
    const classFilter = { year: assignedClass.year, section: assignedClass.section };
    if (department) classFilter.department = department;
    return { $or: [{ instructorId: user.id }, classFilter] };
  }

  return { instructorId: user.id };
}

/**
 * Check whether the given user has permission to access data for a department.
 * Principal → any department; HOD → only their own.
 *
 * @param {{ role, department }} user
 * @param {string} targetDepartment
 * @returns {boolean}
 */
function canAccessDepartment(user, targetDepartment) {
  if (user.role === 'principal') return true;
  if (user.role === 'hod') return user.department === targetDepartment;
  return false;
}

module.exports = { getUserRole, buildSessionFilter, canAccessDepartment };
