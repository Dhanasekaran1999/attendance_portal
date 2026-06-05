# app/routes/attendance.py
from app.utils.token_utils import token_required
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models import Employee, AttendanceRecord
from app.utils.face_utils import verify_face
from app.utils.date_utils import format_date
from datetime import datetime, date
import pytz



IST = pytz.timezone('Asia/Kolkata')
def get_ist_now():
    return datetime.now(IST).replace(tzinfo=None)

attendance_bp = Blueprint('attendance', __name__)

# ─────────────────────────────────────────────
# GET /attendance/today         → Today's attendance list
# ─────────────────────────────────────────────
@attendance_bp.route('/attendance/today', methods=['GET'])
@token_required
def today_attendance():
    today = date.today()

    records = db.session.query(AttendanceRecord, Employee)\
                .join(Employee, AttendanceRecord.employee_id == Employee.id)\
                .filter(AttendanceRecord.date == today)\
                .all()

    result = []
    for record, emp in records:
        result.append({
            'employee_id':   emp.employee_id,
            'name':          emp.name,
            'department':    emp.department,
            'check_in':      record.check_in.strftime('%H:%M:%S') if record.check_in else None,
            'check_out':     record.check_out.strftime('%H:%M:%S') if record.check_out else None,
            'status':        record.status,
            'location': record.location,
            'location_type': record.location_type,
            'face_verified': record.face_verified,
            'location_verified': record.location_verified
        })

    return jsonify({
        'success': True,
        'date': format_date(today),
        'count':   len(result),
        'records': result
    }), 200


# ─────────────────────────────────────────────
# GET /attendance/my/<employee_id>  → Employee's own records
# ─────────────────────────────────────────────
@attendance_bp.route('/attendance/my/<string:employee_id>', methods=['GET'])
@token_required
def my_attendance(employee_id):
    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404

    # Optional month filter: /attendance/my/EMP001?month=2025-01
    month_filter = request.args.get('month')

    query = AttendanceRecord.query.filter_by(employee_id=emp.id)

    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            query = query.filter(
                db.extract('year',  AttendanceRecord.date) == year,
                db.extract('month', AttendanceRecord.date) == month
            )
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid month format. Use YYYY-MM'}), 400

    records = query.order_by(AttendanceRecord.date.desc()).all()

    # Summary counts
    present_days = sum(1 for r in records if r.status == 'Present')
    late_days    = sum(1 for r in records if r.status == 'Late')

    return jsonify({
        'success':      True,
        'employee':     emp.name,
        'employee_id':  emp.employee_id,
        'summary': {
            'total_days':   len(records),
            'present_days': present_days,
            'late_days':    late_days,
            'absent_days':  len(records) - present_days - late_days
        },
        'records': [r.to_dict() for r in records]
    }), 200

# ─────────────────────────────────────────────
# GET /attendance/status/<employee_id>  → Today's status
# ─────────────────────────────────────────────
@attendance_bp.route('/attendance/status/<string:employee_id>', methods=['GET'])
@token_required
def attendance_status(employee_id):
    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404

    today  = date.today()
    record = AttendanceRecord.query.filter_by(
        employee_id=emp.id, date=today
    ).first()

    if not record:
        return jsonify({
            'success':    True,
            'employee':   emp.name,
            'date': format_date(today),
            'checked_in': False,
            'message':    'Not checked in yet today'
        }), 200

    return jsonify({
        'success':      True,
        'employee':     emp.name,
        'date': format_date(today),
        'checked_in':   bool(record.check_in),
        'checked_out':  bool(record.check_out),
        'check_in':     record.check_in.strftime('%H:%M:%S') if record.check_in else None,
        'check_out':    record.check_out.strftime('%H:%M:%S') if record.check_out else None,
        'status':       record.status,
        'hours_worked': round((record.check_out - record.check_in).seconds / 3600, 2)
                        if record.check_in and record.check_out else None
    }), 200