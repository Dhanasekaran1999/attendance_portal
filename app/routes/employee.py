from flask import Blueprint, jsonify
from app.models import Employee, AttendanceRecord

employee_bp = Blueprint('employee', __name__)

# ─────────────────────────────────────────────
# GET /api/profile/<employee_id> → View own profile
# ─────────────────────────────────────────────
@employee_bp.route('/api/profile/<string:employee_id>', methods=['GET'])
def get_profile(employee_id):
    emp = Employee.query.filter_by(employee_id=employee_id).first()

    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404

    return jsonify({
        'success': True,
        'profile': emp.to_dict()
    }), 200


# ─────────────────────────────────────────────
# GET /api/attendance/<employee_id> → View own attendance
# ─────────────────────────────────────────────
@employee_bp.route('/api/attendance/<string:employee_id>', methods=['GET'])
def get_attendance(employee_id):
    emp = Employee.query.filter_by(employee_id=employee_id).first()

    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404

    records = AttendanceRecord.query.filter_by(employee_id=emp.id)\
                .order_by(AttendanceRecord.date.desc()).all()

    return jsonify({
        'success': True,
        'employee': emp.name,
        'total_records': len(records),
        'attendance': [r.to_dict() for r in records]
    }), 200