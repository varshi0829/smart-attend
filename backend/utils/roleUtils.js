const pool = require('../config/db');

async function getUserRole(userId) {
  const { rows } = await pool.query(
    'SELECT role, department, is_class_teacher, assigned_year, assigned_section FROM users WHERE id = $1',
    [userId]
  );
  if (!rows[0]) return null;
  const row = rows[0];
  return {
    role: row.role,
    department: row.department,
    assignedClass: {
      isClassTeacher: row.is_class_teacher,
      year: row.assigned_year,
      section: row.assigned_section
    }
  };
}

/**
 * Build a SQL WHERE fragment + params for session queries.
 * Uses $1, $2... PostgreSQL positional params starting at `startAt`.
 *
 * principal  → all sessions
 * hod        → department only
 * class teacher → own sessions OR assigned class sessions
 * faculty/instructor → own sessions only
 */
function buildSessionFilter(user, startAt = 1) {
  const { role, department, assignedClass } = user;

  if (role === 'principal') {
    return { where: '1=1', params: [] };
  }

  if (role === 'hod') {
    return { where: `s.department = $${startAt}`, params: [department] };
  }

  if (assignedClass?.isClassTeacher) {
    const { year, section } = assignedClass;
    if (department) {
      return {
        where:  `(s.teacher_id = $${startAt} OR (s.year = $${startAt+1} AND s.section = $${startAt+2} AND s.department = $${startAt+3}))`,
        params: [user.id, year, section, department]
      };
    }
    return {
      where:  `(s.teacher_id = $${startAt} OR (s.year = $${startAt+1} AND s.section = $${startAt+2}))`,
      params: [user.id, year, section]
    };
  }

  return { where: `s.teacher_id = $${startAt}`, params: [user.id] };
}

function canAccessDepartment(user, targetDepartment) {
  if (user.role === 'principal') return true;
  if (user.role === 'hod') return user.department === targetDepartment;
  return false;
}

module.exports = { getUserRole, buildSessionFilter, canAccessDepartment };
