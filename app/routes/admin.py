# app/routes/admin.py

from flask import Blueprint, request, jsonify, render_template
from app.extensions import db
from app.models import Employee, AttendanceRecord, AllowedLocation, Holiday
from datetime import datetime, date
import pytz
from dateutil import parser
from app.utils.token_utils import admin_required
import base64
from calendar import monthrange
from app.utils.date_utils import format_date
from app.utils.face_utils import extract_face_encoding
import io
from calendar import monthrange
from flask import send_file
from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side
)
from openpyxl.utils import get_column_letter

IST = pytz.timezone('Asia/Kolkata')
def get_ist_now():
    return datetime.now(IST).replace(tzinfo=None)

# ── Parse dates — accept multiple formats ──
def parse_flexible_date(date_str):
    """Parse date from various formats automatically"""
    if not date_str:
        return None
    try:
        # parse() returns datetime, we convert to date
        return parser.parse(date_str, fuzzy=False).date()
    except (ValueError, OverflowError, TypeError, parser.ParserError):
        return None

admin_bp = Blueprint('admin', __name__)

# GET /admin/employees/all  → All employees with full details
# ─────────────────────────────────────────────
@admin_bp.route('/admin/employees/all', methods=['GET'])
@admin_required
def get_all_employees_details():
    # Optional filters
    filter_active = request.args.get('active')  # true/false
    filter_user_type = request.args.get('user_type')  # Admin/User
    filter_dept = request.args.get('department')  # Engineering etc

    query = Employee.query

    if filter_active is not None:
        is_active = filter_active.lower() == 'true'
        query = query.filter_by(active=is_active)

    if filter_user_type:
        query = query.filter_by(user_type=filter_user_type)

    if filter_dept:
        query = query.filter(Employee.department.ilike(f'%{filter_dept}%'))

    employees = query.order_by(Employee.created_at.asc()).all()

    result = []
    for emp in employees:
        result.append({
            'employee_id': emp.employee_id,
            'name': emp.name,
            'email': emp.email,
            'department': emp.department,
            'designation': emp.designation,
            'phone': emp.phone,
            'user_type': emp.user_type,
            'is_admin': emp.admin,
            'is_active': emp.active,
            'face_registered': emp.face_registered,
            'created_at': emp.created_at.isoformat()
        })

    return jsonify({
        'success': True,
        'count': len(result),
        'employees': result
    }), 200


# ─────────────────────────────────────────────
# GET /admin/employees/<employee_id>  → Get one employee
# ─────────────────────────────────────────────
@admin_bp.route('/admin/employees/<string:employee_id>', methods=['GET'])
@admin_required
def get_employee(employee_id):
    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404

    return jsonify({'success': True, 'employee': emp.to_dict()}), 200


# ─────────────────────────────────────────────
# PUT /admin/employees/<employee_id>/edit  → Edit employee
# form-data: name, designation, phone, active
# ─────────────────────────────────────────────
@admin_bp.route('/admin/employees/<string:employee_id>/edit', methods=['PUT'])
@admin_required
def edit_employee(employee_id):

    # ── Find employee ──
    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404

    # ── Get form fields ──
    name        = request.form.get('name', '').strip()
    designation = request.form.get('designation', '').strip()
    phone       = request.form.get('phone', '').strip()
    active      = request.form.get('active', '').strip().lower()
    user_type   = request.form.get('user_type', '').strip()

    # ── Track updated fields ──
    updated = []

    # ── Validate and update name ──
    if name:
        emp.name = name
        updated.append('name')

    # ── Validate and update designation ──
    if designation:
        emp.designation = designation
        updated.append('designation')

    # ── Validate and update phone ──
    if phone:
        if not phone.isdigit():
            return jsonify({
                'success': False,
                'message': 'Phone must contain digits only. No spaces or symbols.'
            }), 400
        if len(phone) != 10:
            return jsonify({
                'success': False,
                'message': f'Phone must be exactly 10 digits. You entered {len(phone)}.'
            }), 400
        emp.phone = phone
        updated.append('phone')

    # ── Validate and update active ──
    if active:
        if active not in ['true', 'false']:
            return jsonify({
                'success': False,
                'message': 'active must be true or false'
            }), 400
        emp.active = active == 'true'
        updated.append('active')

    # ── Validate and update user_type ──
    if user_type:
        if user_type not in ['Admin', 'User']:
            return jsonify({
                'success': False,
                'message': 'user_type must be Admin or User'
            }), 400
        emp.user_type = user_type
        emp.admin     = True if user_type == 'Admin' else False
        updated.append('user_type')

    # ── Update face if provided ──
    if 'face_image' in request.files:
        file = request.files['face_image']

        if file.filename != '':
            file_bytes    = file.read()
            base64_string = base64.b64encode(file_bytes).decode('utf-8')
            face_image    = f"data:image/jpeg;base64,{base64_string}"

            encoding, message = extract_face_encoding(face_image)

            if encoding is None:
                return jsonify({
                    'success': False,
                    'message': f'Face detection failed — {message}',
                    'hint':    'Make sure: good lighting, only one face, looking straight at camera'
                }), 400

            emp.face_encoding   = encoding
            emp.face_registered = True
            updated.append('face_image')

    # ── Nothing was sent ──
    if not updated:
        return jsonify({
            'success': False,
            'message': 'No fields provided to update. Send at least one field.'
        }), 400

    db.session.commit()

    return jsonify({
        'success':        True,
        'message':        f'{emp.name} updated successfully',
        'updated_fields': updated,
        'employee': {
            'employee_id':     emp.employee_id,
            'name':            emp.name,
            'designation':     emp.designation,
            'phone':           emp.phone,
            'department':      emp.department,
            'email':           emp.email,
            'user_type':       emp.user_type,
            'is_active':       emp.active,
            'is_admin':        emp.admin,
            'face_registered': emp.face_registered
        }
    }), 200


# ─────────────────────────────────────────────
# POST /admin/create-employee   → Admin only, create new employee
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# POST /admin/create-employee-with-face
# Create employee + register face in one shot
# ─────────────────────────────────────────────
@admin_bp.route('/admin/create-employee-with-face', methods=['POST'])
@admin_required
def create_employee_with_face():
    import base64
    import re
    from app.utils.face_utils import extract_face_encoding

    # ── Get all form fields ──
    requester_id = request.form.get('requester_id', '').strip()
    employee_id  = request.form.get('employee_id', '').strip()
    name         = request.form.get('name', '').strip()
    email        = request.form.get('email', '').strip()
    department   = request.form.get('department', '').strip()
    designation  = request.form.get('designation', '').strip()
    phone        = request.form.get('phone', '').strip()
    user_type    = request.form.get('user_type', 'User').strip()
    password     = request.form.get('password', '').strip()

    # ─────────────────────────────────────────────
    # VALIDATION 1 — Required fields check
    # ─────────────────────────────────────────────
    required_fields = {
        'requester_id': requester_id,
        'employee_id':  employee_id,
        'name':         name,
        'email':        email,
        'phone':        phone,
        'designation':  designation,
        'password':     password
    }

    for field_name, value in required_fields.items():
        if not value:
            return jsonify({
                'success': False,
                'message': f'{field_name.replace("_", " ").title()} is required'
            }), 400

    # ─────────────────────────────────────────────
    # VALIDATION 2 — Email format
    # ─────────────────────────────────────────────
    email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w{2,}$'
    if not re.match(email_pattern, email):
        return jsonify({
            'success': False,
            'message': 'Invalid email format. Example: arjun@company.com'
        }), 400

    # ─────────────────────────────────────────────
    # VALIDATION 3 — Phone number (exactly 10 digits)
    # ─────────────────────────────────────────────
    if not phone.isdigit():
        return jsonify({
            'success': False,
            'message': 'Phone number must contain digits only. No spaces or symbols.'
        }), 400

    if len(phone) != 10:
        return jsonify({
            'success': False,
            'message': f'Phone number must be exactly 10 digits. You entered {len(phone)} digits.'
        }), 400

    # ─────────────────────────────────────────────
    # VALIDATION 4 — Password minimum 6 characters
    # ─────────────────────────────────────────────
    if len(password) < 6:
        return jsonify({
            'success': False,
            'message': 'Password must be at least 6 characters long.'
        }), 400

    # ─────────────────────────────────────────────
    # VALIDATION 5 — user_type must be Admin or User
    # ─────────────────────────────────────────────
    if user_type not in ['Admin', 'User']:
        return jsonify({
            'success': False,
            'message': 'user_type must be either Admin or User'
        }), 400

    # ─────────────────────────────────────────────
    # VALIDATION 6 — Face image is MANDATORY
    # ─────────────────────────────────────────────
    if 'face_image' not in request.files:
        return jsonify({
            'success': False,
            'message': 'Face image is mandatory. Please capture face photo.'
        }), 400

    file = request.files['face_image']

    if file.filename == '':
        return jsonify({
            'success': False,
            'message': 'Face image is mandatory. No file was selected.'
        }), 400

    # ─────────────────────────────────────────────
    # VALIDATION 7 — Requester must exist and be Admin
    # ─────────────────────────────────────────────
    requester = Employee.query.filter_by(
        employee_id=requester_id, active=True
    ).first()

    if not requester:
        return jsonify({
            'success': False,
            'message': f'Requester {requester_id} not found or inactive'
        }), 404

    if not requester.admin:
        return jsonify({
            'success': False,
            'message': 'Access denied. Only Admins can create employees.'
        }), 403

    # ─────────────────────────────────────────────
    # VALIDATION 8 — Duplicate employee_id and email
    # ─────────────────────────────────────────────
    if Employee.query.filter_by(employee_id=employee_id).first():
        return jsonify({
            'success': False,
            'message': f'Employee ID {employee_id} already exists'
        }), 409

    if Employee.query.filter_by(email=email).first():
        return jsonify({
            'success': False,
            'message': f'Email {email} is already registered'
        }), 409

    # ─────────────────────────────────────────────
    # PROCESS — Extract face encoding (Mandatory)
    # ─────────────────────────────────────────────
    file_bytes    = file.read()
    base64_string = base64.b64encode(file_bytes).decode('utf-8')
    face_image    = f"data:image/jpeg;base64,{base64_string}"

    encoding, msg = extract_face_encoding(face_image)

    if encoding is None:
        return jsonify({
            'success': False,
            'message': f'Face detection failed — {msg}',
            'hint':    'Make sure: face is clearly visible, good lighting, only one person in frame, looking straight at camera'
        }), 400

    # ─────────────────────────────────────────────
    # SAVE — Create employee with face
    # ─────────────────────────────────────────────
    emp = Employee(
        employee_id     = employee_id,
        name            = name,
        email           = email,
        department      = department,
        designation     = designation,
        phone           = phone,
        user_type       = user_type,
        admin           = True if user_type == 'Admin' else False,
        active          = True,
        face_encoding   = encoding,
        face_registered = True
    )
    emp.set_password(password)

    db.session.add(emp)
    db.session.commit()

    return jsonify({
        'success':     True,
        'message':     f'Employee {name} created successfully with face registration!',
        'employee': {
            'id':              emp.id,
            'employee_id':     emp.employee_id,
            'name':            emp.name,
            'email':           emp.email,
            'department':      emp.department,
            'designation':     emp.designation,
            'phone':           emp.phone,
            'user_type':       emp.user_type,
            'admin':           emp.admin,
            'active':          emp.active,
            'face_registered': emp.face_registered,
            'created_at':      emp.created_at.isoformat()
        }
    }), 201


# ─────────────────────────────────────────────
# POST /admin/verify-face-capture
# Test: check if a captured photo has a valid face
# Use this BEFORE submitting the full form
# ─────────────────────────────────────────────
@admin_bp.route('/admin/verify-face-capture', methods=['POST'])
def verify_face_capture():
    import base64
    from app.utils.face_utils import extract_face_encoding

    if 'face_image' not in request.files:
        return jsonify({
            'success': False,
            'message': 'face_image is required'
        }), 400

    file = request.files['face_image']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400

    # Convert to base64
    file_bytes    = file.read()
    base64_string = base64.b64encode(file_bytes).decode('utf-8')
    face_image    = f"data:image/jpeg;base64,{base64_string}"

    # Check if face is detectable
    encoding, message = extract_face_encoding(face_image)

    if encoding is None:
        return jsonify({
            'success': False,
            'message': message,
            'face_detected': False
        }), 400

    return jsonify({
        'success':        True,
        'message':        'Face detected successfully! Ready to save.',
        'face_detected':  True,
        'encoding_points': len(encoding)
    }), 200


# ─────────────────────────────────────────────
# GET /admin/attendance/live     → Live today's attendance feed
# ─────────────────────────────────────────────
@admin_bp.route('/admin/attendance/live', methods=['GET'])
@admin_required
def live_attendance():
    today = date.today()

    records = db.session.query(AttendanceRecord, Employee)\
                .join(Employee, AttendanceRecord.employee_id == Employee.id)\
                .filter(AttendanceRecord.date == today)\
                .order_by(AttendanceRecord.created_at.desc())\
                .all()

    result = []
    for record, emp in records:
        # Calculate hours worked if checked out
        hours_worked = None
        if record.check_in and record.check_out:
            seconds      = (record.check_out - record.check_in).seconds
            hours_worked = round(seconds / 3600, 2)

        result.append({
            'employee_id':  emp.employee_id,
            'name':         emp.name,
            'designation':  emp.designation,
            'department':   emp.department,
            'user_type':    emp.user_type,
            'check_in':     record.check_in.strftime('%H:%M:%S') if record.check_in else None,
            'check_out':    record.check_out.strftime('%H:%M:%S') if record.check_out else None,
            'status':       record.status,
            'hours_worked': hours_worked,
            'location': record.location,
            'location_type': record.location_type,
            'face_verified':     record.face_verified,
            'location_verified': record.location_verified
        })

    # Summary counts
    total_employees = Employee.query.filter_by(active=True).count()
    present_count   = len(result)
    checked_out     = sum(1 for r in result if r['check_out'])
    still_in        = present_count - checked_out

    return jsonify({
        'success': True,
        'date': format_date(today),
        'summary': {
            'total_employees': total_employees,
            'present_today':   present_count,
            'absent_today':    total_employees - present_count,
            'checked_out':     checked_out,
            'still_in_office': still_in
        },
        'attendance': result
    }), 200

# ─────────────────────────────────────────────
# POST /admin/attendance/filter
# form-data: from_date, to_date (mandatory)
#            employee_id        (optional)
# ─────────────────────────────────────────────
@admin_bp.route('/admin/attendance/filter', methods=['POST'])
@admin_required
def filter_attendance():

    # ── Mandatory filters ──
    from_date_str = request.form.get('from_date', '').strip()
    to_date_str   = request.form.get('to_date', '').strip()

    # ── Optional filter ──
    filter_employee_id = request.form.get('employee_id', '').strip()

    # ── Validate mandatory fields ──
    if not from_date_str:
        return jsonify({
            'success': False,
            'message': 'from_date is required. Format: DD-MM-YYYY'
        }), 400

    if not to_date_str:
        return jsonify({
            'success': False,
            'message': 'to_date is required. Format: DD-MM-YYYY'
        }), 400

    # ── Parse from_date ──
    from_date = parse_flexible_date(from_date_str)
    if not from_date:
        return jsonify({
            'success': False,
            'message': f'Invalid from_date: "{from_date_str}". Please provide a valid date format.'
        }), 400

    # ── Parse to_date ──
    to_date = parse_flexible_date(to_date_str)
    if not to_date:
        return jsonify({
            'success': False,
            'message': f'Invalid to_date: "{to_date_str}". Please provide a valid date format.'
        }), 400

    # ── Validate date range ──
    if from_date > to_date:
        return jsonify({
            'success': False,
            'message': 'from_date cannot be greater than to_date'
        }), 400

    # ── Build query ──
    query = db.session.query(AttendanceRecord, Employee)\
                .join(Employee, AttendanceRecord.employee_id == Employee.id)\
                .filter(
                    AttendanceRecord.date >= from_date,
                    AttendanceRecord.date <= to_date
                )

    # ── Apply optional employee_id filter ──
    if filter_employee_id:
        emp = Employee.query.filter_by(employee_id=filter_employee_id).first()
        if not emp:
            return jsonify({
                'success': False,
                'message': f'Employee {filter_employee_id} not found'
            }), 404
        query = query.filter(AttendanceRecord.employee_id == emp.id)

    # ── Order latest first ──
    records = query.order_by(
        AttendanceRecord.date.desc(),
        AttendanceRecord.created_at.desc()
    ).all()

    # ── Build result ──
    result = []
    for record, emp in records:

        hours_worked = None
        if record.check_in and record.check_out:
            seconds      = (record.check_out - record.check_in).seconds
            hours_worked = round(seconds / 3600, 2)

        result.append({
            'date':          format_date(record.date),
            'employee_id':   emp.employee_id,
            'name':          emp.name,
            'designation':   emp.designation,
            'department':    emp.department,
            'user_type':     emp.user_type,
            'check_in':      record.check_in.strftime('%H:%M:%S')  if record.check_in  else None,
            'check_out':     record.check_out.strftime('%H:%M:%S') if record.check_out else None,
            'status':        record.status,
            'hours_worked':  hours_worked,
            'location_type': record.location_type,
            'location':      record.location,
            'face_verified': record.face_verified
        })

    # ── Summary ──
    present_count = sum(1 for r in result if r['status'] == 'Present')
    late_count    = sum(1 for r in result if r['status'] == 'Late')

    return jsonify({
        'success':     True,
        'from_date':   format_date(from_date),
        'to_date':     format_date(to_date),
        'employee_id': filter_employee_id or 'All',
        'summary': {
            'total_records': len(result),
            'present':       present_count,
            'late':          late_count,
        },
        'records': result
    }), 200


# ─────────────────────────────────────────────
# DELETE /admin/employees/<employee_id>  → Soft delete
# ─────────────────────────────────────────────
@admin_bp.route('/admin/employees/<string:employee_id>', methods=['DELETE'])
@admin_required
def delete_employee(employee_id):
    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404

    name = emp.name

    # ── Delete attendance records first ──
    AttendanceRecord.query.filter_by(employee_id=emp.id).delete()

    # ── Delete allowed locations ──
    AllowedLocation.query.filter_by(employee_id=emp.id).delete()

    # ── Now delete employee ──
    db.session.delete(emp)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'{name} has been permanently deleted'
    }), 200


# ─────────────────────────────────────────────
# PUT /admin/employees/<employee_id>/activate  → Re-activate
# ─────────────────────────────────────────────
@admin_bp.route('/admin/employees/<string:employee_id>/activate', methods=['PUT'])
@admin_required
def activate_employee(employee_id):
    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404

    emp.active = True
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'{emp.name} has been activated'
    }), 200


# ─────────────────────────────────────────────
# DELETE /admin/employees/<employee_id>/face   → Reset face
# ─────────────────────────────────────────────
@admin_bp.route('/admin/employees/<string:employee_id>/face', methods=['DELETE'])
def reset_face(employee_id):
    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404

    emp.face_encoding   = None
    emp.face_registered = False
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Face data reset for {emp.name}. They must re-register.'
    }), 200


# ─────────────────────────────────────────────
# GET /admin/attendance          → All attendance records
# ─────────────────────────────────────────────
@admin_bp.route('/admin/attendance', methods=['GET'])
@admin_required
def get_all_attendance():
    # Optional filters via query params
    # e.g. /admin/attendance?date=2025-01-15&department=Engineering
    filter_date       = request.args.get('date')
    filter_department = request.args.get('department')
    filter_status     = request.args.get('status')

    query = db.session.query(AttendanceRecord, Employee)\
                .join(Employee, AttendanceRecord.employee_id == Employee.id)

    if filter_date:
        try:
            parsed_date = datetime.strptime(filter_date, '%Y-%m-%d').date()
            query = query.filter(AttendanceRecord.date == parsed_date)
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD'}), 400

    if filter_department:
        query = query.filter(Employee.department.ilike(f'%{filter_department}%'))

    if filter_status:
        query = query.filter(AttendanceRecord.status == filter_status)

    records = query.order_by(AttendanceRecord.date.desc()).all()

    result = []
    for record, emp in records:
        data = record.to_dict()
        data['employee_name']  = emp.name
        data['employee_id']    = emp.employee_id
        data['department']     = emp.department
        result.append(data)

    return jsonify({
        'success': True,
        'count':   len(result),
        'records': result
    }), 200


# ─────────────────────────────────────────────
# GET /admin/attendance/<employee_id>  → One employee's attendance
# ─────────────────────────────────────────────
@admin_bp.route('/admin/attendance/<string:employee_id>', methods=['GET'])
@admin_required
def get_employee_attendance(employee_id):
    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404

    records = AttendanceRecord.query\
                .filter_by(employee_id=emp.id)\
                .order_by(AttendanceRecord.date.desc())\
                .all()

    return jsonify({
        'success':       True,
        'employee':      emp.name,
        'employee_id':   emp.employee_id,
        'department':    emp.department,
        'total_records': len(records),
        'attendance':    [r.to_dict() for r in records]
    }), 200

# ─────────────────────────────────────────────
# POST /admin/change-password
# Admin can change any employee's password
# ─────────────────────────────────────────────
@admin_bp.route('/admin/change-password', methods=['POST'])
@admin_required
def change_password():
    requester_id = request.form.get('requester_id', '').strip()
    employee_id  = request.form.get('employee_id', '').strip()
    new_password = request.form.get('new_password', '').strip()

    # ── Validate required fields ──
    if not requester_id:
        return jsonify({'success': False, 'message': 'requester_id is required'}), 400

    if not employee_id:
        return jsonify({'success': False, 'message': 'employee_id is required'}), 400

    if not new_password:
        return jsonify({'success': False, 'message': 'new_password is required'}), 400

    # ── Validate password length ──
    if len(new_password) < 6:
        return jsonify({
            'success': False,
            'message': 'Password must be at least 6 characters long.'
        }), 400

    # ── Find requester ──
    requester = Employee.query.filter_by(
        employee_id = requester_id,
        active      = True
    ).first()

    if not requester:
        return jsonify({
            'success': False,
            'message': f'Requester {requester_id} not found or inactive'
        }), 404

    # ── Check admin ──
    if not requester.admin:
        return jsonify({
            'success': False,
            'message': 'Access denied. Only Admins can change passwords.'
        }), 403

    # ── Find target employee ──
    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({
            'success': False,
            'message': f'Employee {employee_id} not found'
        }), 404

    # ── Change password ──
    emp.set_password(new_password)
    db.session.commit()

    return jsonify({
        'success':     True,
        'message':     f'Password changed successfully for {emp.name}!',
        'employee_id': emp.employee_id,
        'name':        emp.name
    }), 200


@admin_bp.route('/admin/attendance/monthly-sheet', methods=['POST'])
@admin_required
def monthly_attendance_sheet():

    # ── Get month and year from form-data ──
    month_input = request.form.get('month', '').strip()
    year_input  = request.form.get('year', '').strip()

    # ── Default to current month and year ──
    today        = date.today()
    target_month = int(month_input) if month_input else today.month
    target_year  = int(year_input)  if year_input  else today.year

    # ── Validate month ──
    if not (1 <= target_month <= 12):
        return jsonify({
            'success': False,
            'message': 'month must be between 1 and 12'
        }), 400

    # ── Get total days in month ──
    total_days_in_month = monthrange(target_year, target_month)[1]

    # ── Get all active employees ──
    employees = Employee.query.filter_by(active=True)\
                    .order_by(Employee.created_at.asc()).all()

    # ── Get all attendance records for this month ──
    from_date = date(target_year, target_month, 1)
    to_date   = date(target_year, target_month, total_days_in_month)

    all_records = db.session.query(AttendanceRecord)\
                    .filter(
                        AttendanceRecord.date >= from_date,
                        AttendanceRecord.date <= to_date
                    ).all()

    # ── Build lookup dict: {employee_id: {day: {status, location_type}}} ──
    attendance_lookup = {}
    for record in all_records:
        emp_id = record.employee_id
        day    = record.date.day
        if emp_id not in attendance_lookup:
            attendance_lookup[emp_id] = {}

        hours_worked = None
        if record.check_in and record.check_out:
            seconds = (record.check_out - record.check_in).seconds
            hours_worked = round(seconds / 3600, 2)

        attendance_lookup[emp_id][day] = {
            'status':        record.status,
            'location_type': record.location_type,
            'hours_worked': hours_worked
        }

    # ── Find Sundays ──
    sunday_days = [
        d for d in range(1, total_days_in_month + 1)
        if date(target_year, target_month, d).weekday() == 6
    ]

    # ── Fetch holidays from DB for this month ──
    db_holidays = Holiday.query.filter(
        db.extract('year', Holiday.holiday_date) == target_year,
        db.extract('month', Holiday.holiday_date) == target_month
    ).all()

    # ── Build holiday lookup {day: holiday_name} ──
    holiday_lookup = {h.holiday_date.day: h.holiday_name for h in db_holidays}

    # ── All holiday days = sundays + db holidays ──
    all_holiday_days = set(sunday_days) | set(holiday_lookup.keys())

    # ── Build result for each employee ──
    result = []
    for idx, emp in enumerate(employees, start=1):

        daily_status = {}
        present_days = 0
        absent_days  = 0
        wfh_days     = 0
        h_days       = len(all_holiday_days)  # H = Holiday (Sunday)

        for d in range(1, total_days_in_month + 1):
            current_date = date(target_year, target_month, d)

            # ── Future dates ──
            if current_date > today:
                daily_status[str(d)] = {
                    'code': '-',
                    'hours_worked': None
                }

            # ── Sunday = H (Holiday) ──
            elif d in all_holiday_days:
                daily_status[str(d)] = {
                    'code': 'H',
                    'hours_worked': None
                }

            # ── Check attendance record ──
            elif emp.id in attendance_lookup and d in attendance_lookup[emp.id]:
                rec = attendance_lookup[emp.id][d]
                status = rec['status']
                location_type = rec['location_type']
                hours_worked = rec['hours_worked']

                # ── Not Office = WFH ──
                if location_type and location_type != 'Office':
                    daily_status[str(d)] = {
                        'code': 'WFH',
                        'hours_worked': hours_worked
                    }
                    wfh_days += 1

                else:
                    daily_status[str(d)] = {
                        'code': 'P',
                        'hours_worked': hours_worked
                    }
                    present_days += 1

            # ── Absent ──
            else:
                daily_status[str(d)] = {
                    'code': 'A',
                    'hours_worked': None
                }
                absent_days += 1

        # ── Working days = total days - Sundays ──
        working_days = total_days_in_month - h_days

        sorted_status = {
            str(d): daily_status[str(d)]
            for d in range(1, total_days_in_month + 1)
            if str(d) in daily_status
        }

        total_hours = sum(
            v['hours_worked']
            for v in daily_status.values()
            if isinstance(v, dict) and v['hours_worked'] is not None
        )

        result.append({
            'sno':          idx,
            'employee_id':  emp.employee_id,
            'name':         emp.name,
            'department':   emp.department,
            'designation':  emp.designation,
            'daily_status': sorted_status,
            'summary': {
                'present_days':   present_days,
                'wfh_days':       wfh_days,
                'absent_days':    absent_days,
                'holidays':       h_days,
                'working_days':   working_days,
                'days_worked': present_days + wfh_days,
                'total_days':     total_days_in_month,
                'total_hours_worked': round(total_hours, 2)
            }
        })

    return jsonify({
        'success':         True,
        'month':           target_month,
        'year':            target_year,
        'month_name':      date(target_year, target_month, 1).strftime('%B %Y'),
        'total_days':      total_days_in_month,
        'total_employees': len(result),
        'sheet':           result
    }), 200


# ─────────────────────────────────────────────
# POST /admin/attendance/monthly-sheet/export
# Download monthly attendance sheet as Excel
# form-data: month (optional), year (optional)
# ─────────────────────────────────────────────
@admin_bp.route('/admin/attendance/monthly-sheet/export', methods=['POST'])
@admin_required
def export_monthly_attendance_excel():

    # ── Get month and year ──
    month_input = request.form.get('month', '').strip()
    year_input  = request.form.get('year', '').strip()

    today        = date.today()
    target_month = int(month_input) if month_input else today.month
    target_year  = int(year_input)  if year_input  else today.year

    if not (1 <= target_month <= 12):
        return jsonify({'success': False, 'message': 'month must be between 1 and 12'}), 400

    total_days_in_month = monthrange(target_year, target_month)[1]
    month_name          = date(target_year, target_month, 1).strftime('%B %Y')

    # ── Get employees ──
    employees = Employee.query.filter_by(active=True)\
                    .order_by(Employee.created_at.asc()).all()

    # ── Get attendance records ──
    from_date   = date(target_year, target_month, 1)
    to_date     = date(target_year, target_month, total_days_in_month)
    all_records = db.session.query(AttendanceRecord)\
                    .filter(
                        AttendanceRecord.date >= from_date,
                        AttendanceRecord.date <= to_date
                    ).all()

    # ── Build lookup ──
    attendance_lookup = {}
    for record in all_records:
        emp_id = record.employee_id
        day    = record.date.day
        if emp_id not in attendance_lookup:
            attendance_lookup[emp_id] = {}
        hours_worked = None
        if record.check_in and record.check_out:
            seconds      = (record.check_out - record.check_in).seconds
            hours_worked = round(seconds / 3600, 2)
        attendance_lookup[emp_id][day] = {
            'status':        record.status,
            'location_type': record.location_type,
            'hours_worked':  hours_worked
        }

    # ── Find Sundays ──
    sunday_days = [
        d for d in range(1, total_days_in_month + 1)
        if date(target_year, target_month, d).weekday() == 6
    ]

    # ── Fetch holidays from DB for this month ──
    db_holidays = Holiday.query.filter(
        db.extract('year', Holiday.holiday_date) == target_year,
        db.extract('month', Holiday.holiday_date) == target_month
    ).all()

    # ── Build holiday lookup {day: holiday_name} ──
    holiday_lookup = {h.holiday_date.day: h.holiday_name for h in db_holidays}

    # ── All holiday days = sundays + db holidays ──
    all_holiday_days = set(sunday_days) | set(holiday_lookup.keys())

    # ── Define styles ──
    def make_border():
        side = Side(style='thin', color='CCCCCC')
        return Border(left=side, right=side, top=side, bottom=side)

    header_fill    = PatternFill('solid', start_color='1F3864')   # dark blue
    subheader_fill = PatternFill('solid', start_color='2E75B6')   # medium blue
    sunday_fill    = PatternFill('solid', start_color='D6E4F0')   # light blue
    present_fill   = PatternFill('solid', start_color='E2EFDA')   # light green
    late_fill      = PatternFill('solid', start_color='FFF2CC')   # light yellow
    absent_fill    = PatternFill('solid', start_color='FCE4D6')   # light red
    wfh_fill       = PatternFill('solid', start_color='EAD1DC')   # light purple
    summary_fill   = PatternFill('solid', start_color='F2F2F2')   # light grey

    white_bold  = Font(name='Arial', bold=True, color='FFFFFF', size=10)
    white_font  = Font(name='Arial', color='FFFFFF', size=9)
    black_bold  = Font(name='Arial', bold=True, color='000000', size=10)
    black_font  = Font(name='Arial', color='000000', size=9)
    center      = Alignment(horizontal='center', vertical='center')
    left_align        = Alignment(horizontal='left',   vertical='center')

    # ── Create workbook ──
    wb = Workbook()
    ws = wb.active
    ws.title = f'Attendance {month_name}'
    ws.freeze_panes = 'D3'   # freeze S.No, Name, Designation columns

    # ── Row 1: Title ──
    total_cols = 3 + total_days_in_month + 8  # sno+name+desig + days + summary cols
    ws.merge_cells(start_row=1, start_column=1,
                   end_row=1,   end_column=total_cols)
    title_cell           = ws.cell(row=1, column=1)
    title_cell.value     = f'MONTHLY ATTENDANCE SHEET — {month_name.upper()}'
    title_cell.font      = Font(name='Arial', bold=True, color='FFFFFF', size=13)
    title_cell.fill      = header_fill
    title_cell.alignment = center
    ws.row_dimensions[1].height = 28

    # ── Row 2: Column headers ──
    headers = ['S.No', 'Name', 'Emp ID']
    for d in range(1, total_days_in_month + 1):
        headers.append(str(d))
    headers += ['Present', 'WFH', 'Absent', 'Holidays',
                'Working Days', 'Days Worked', 'Total Hours', 'Total Days']

    for col, header in enumerate(headers, start=1):
        cell            = ws.cell(row=2, column=col, value=header)
        cell.font       = white_bold
        cell.fill       = subheader_fill
        cell.alignment  = center
        cell.border     = make_border()

    ws.row_dimensions[2].height = 20

    # ── Set column widths ──
    ws.column_dimensions['A'].width = 6    # S.No
    ws.column_dimensions['B'].width = 22   # Name
    ws.column_dimensions['C'].width = 10   # Emp ID
    for col in range(4, 4 + total_days_in_month):
        ws.column_dimensions[get_column_letter(col)].width = 5
    # Summary columns
    for i, w in enumerate([9, 6, 7, 8, 12, 11, 12, 10], start=4 + total_days_in_month):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ── Data rows ──
    for idx, emp in enumerate(employees, start=1):
        row = idx + 2   # data starts at row 3

        present_days = absent_days = wfh_days = 0
        h_days       = len(all_holiday_days)
        total_hours  = 0.0

        # S.No, Name, Designation
        for col, val in enumerate([idx, emp.name, emp.employee_id], start=1):
            cell            = ws.cell(row=row, column=col, value=val)
            cell.font       = black_bold if col == 2 else black_font
            cell.alignment  = left_align if col == 2 else center
            cell.border     = make_border()

        # Daily columns
        for d in range(1, total_days_in_month + 1):
            col          = d + 3
            current_date = date(target_year, target_month, d)
            cell         = ws.cell(row=row, column=col)
            cell.alignment = center
            cell.border    = make_border()
            cell.font      = black_font

            if current_date > today:
                cell.value = '-'

            elif d in all_holiday_days:
                cell.value = 'H'
                cell.fill  = sunday_fill
                cell.font  = Font(name='Arial', color='1F3864', size=9, bold=True)

            elif emp.id in attendance_lookup and d in attendance_lookup[emp.id]:
                rec           = attendance_lookup[emp.id][d]
                status        = rec['status']
                location_type = rec['location_type']
                hw            = rec['hours_worked'] or 0

                if location_type and location_type != 'Office':
                    cell.value = 'WFH'
                    cell.fill  = wfh_fill
                    wfh_days  += 1
                    total_hours += hw
                else:
                    cell.value = 'P'
                    cell.fill  = present_fill
                    present_days += 1
                    total_hours  += hw
            else:
                cell.value = 'A'
                cell.fill  = absent_fill
                absent_days += 1

        # Summary columns
        summary_col  = 4 + total_days_in_month
        working_days = total_days_in_month - h_days
        summary_vals = [
            present_days,
            wfh_days,
            absent_days,
            h_days,
            working_days,  # ← Working Days
            present_days + wfh_days,  # ← Days Worked
            round(total_hours, 2),  # ← Total Hours
            total_days_in_month  # ← Total Days
        ]
        for i, val in enumerate(summary_vals):
            cell            = ws.cell(row=row, column=summary_col + i, value=val)
            cell.fill       = summary_fill
            cell.font       = black_font
            cell.alignment  = center
            cell.border     = make_border()

        ws.row_dimensions[row].height = 16

    # ── Legend row at bottom ──
    legend_row = len(employees) + 4

    # "Legend:" in column C (column 3)
    legend_label = ws.cell(row=legend_row, column=3, value='Legend:')
    legend_label.font = black_bold
    legend_label.alignment = left_align

    legends = [
        ('P', 'Present', present_fill),
        ('WFH', 'Work From Home', wfh_fill),
        ('A', 'Absent', absent_fill),
        ('H', 'Holiday', sunday_fill),  # ← removed "Sunday"
    ]
    for i, (code, label, fill) in enumerate(legends):
        c1 = ws.cell(row=legend_row, column=4 + i * 2, value=code)  # ← starts from col 4
        c1.fill = fill
        c1.font = black_bold
        c1.alignment = center
        c1.border = make_border()
        c2 = ws.cell(row=legend_row, column=5 + i * 2, value=label)  # ← starts from col 5
        c2.font = black_font
        c2.alignment = left_align

    # ── Save to buffer ──
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    timestamp = get_ist_now().strftime('%d%m%Y_%H%M%S')
    filename = f'Attendance_{month_name.replace(" ", "_")}_{timestamp}.xlsx'

    return send_file(
        buffer,
        as_attachment      = True,
        download_name      = filename,
        mimetype           = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# ─────────────────────────────────────────────
# POST /admin/attendance/timesheet
# Employee-wise timesheet for a month (check-in/out per day)
# ─────────────────────────────────────────────
@admin_bp.route('/admin/attendance/timesheet', methods=['POST'])
@admin_required
def timesheet():
    month_input = request.form.get('month', '').strip()
    year_input  = request.form.get('year',  '').strip()

    today        = date.today()
    target_month = int(month_input) if month_input else today.month
    target_year  = int(year_input)  if year_input  else today.year

    if not (1 <= target_month <= 12):
        return jsonify({'success': False, 'message': 'month must be between 1 and 12'}), 400

    total_days_in_month = monthrange(target_year, target_month)[1]
    from_date = date(target_year, target_month, 1)
    to_date   = date(target_year, target_month, total_days_in_month)

    employees   = Employee.query.filter_by(active=True).order_by(Employee.created_at.asc()).all()
    all_records = db.session.query(AttendanceRecord).filter(
        AttendanceRecord.date >= from_date,
        AttendanceRecord.date <= to_date
    ).all()

    # Build lookup: {employee_db_id: {day: record_dict}}
    lookup = {}
    for rec in all_records:
        lookup.setdefault(rec.employee_id, {})[rec.date.day] = rec

    # Sundays + DB holidays
    sunday_days   = [d for d in range(1, total_days_in_month + 1)
                     if date(target_year, target_month, d).weekday() == 6]
    db_holidays   = Holiday.query.filter(
        db.extract('year',  Holiday.holiday_date) == target_year,
        db.extract('month', Holiday.holiday_date) == target_month
    ).all()
    holiday_lookup   = {h.holiday_date.day: h.holiday_name for h in db_holidays}
    all_holiday_days = set(sunday_days) | set(holiday_lookup.keys())

    DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    result = []
    for idx, emp in enumerate(employees, start=1):
        days      = {}
        total_hrs = 0.0
        present   = wfh = absent = 0

        for d in range(1, total_days_in_month + 1):
            cur = date(target_year, target_month, d)
            day_name = DAY_NAMES[cur.weekday()]

            if cur > today:
                days[str(d)] = {'day': day_name, 'type': 'future',
                                 'check_in': None, 'check_out': None,
                                 'hours': None, 'location': None}
            elif d in all_holiday_days:
                days[str(d)] = {'day': day_name, 'type': 'holiday',
                                 'label': holiday_lookup.get(d, 'Sunday'),
                                 'check_in': None, 'check_out': None,
                                 'hours': None, 'location': None}
            elif emp.id in lookup and d in lookup[emp.id]:
                rec = lookup[emp.id][d]
                hrs = None
                if rec.check_in and rec.check_out:
                    hrs = round((rec.check_out - rec.check_in).seconds / 3600, 2)
                    total_hrs += hrs
                loc_type = rec.location_type or 'Office'
                rec_type = 'wfh' if loc_type != 'Office' else 'present'
                if rec_type == 'wfh':
                    wfh += 1
                else:
                    present += 1
                days[str(d)] = {
                    'day':       day_name,
                    'type':      rec_type,
                    'check_in':  rec.check_in.strftime('%H:%M')  if rec.check_in  else None,
                    'check_out': rec.check_out.strftime('%H:%M') if rec.check_out else None,
                    'hours':     hrs,
                    'location':  loc_type
                }
            else:
                absent += 1
                days[str(d)] = {'day': day_name, 'type': 'absent',
                                 'check_in': None, 'check_out': None,
                                 'hours': None, 'location': None}

        working_days = total_days_in_month - len(all_holiday_days)
        result.append({
            'sno':         idx,
            'employee_id': emp.employee_id,
            'name':        emp.name,
            'department':  emp.department,
            'designation': emp.designation,
            'phone':       emp.phone,
            'email':       emp.email,
            'days':        days,
            'summary': {
                'present':      present,
                'wfh':          wfh,
                'absent':       absent,
                'holidays':     len(all_holiday_days),
                'working_days': working_days,
                'days_worked':  present + wfh,
                'total_hours':  round(total_hrs, 2),
            }
        })

    return jsonify({
        'success':         True,
        'month':           target_month,
        'year':            target_year,
        'month_name':      date(target_year, target_month, 1).strftime('%B %Y'),
        'total_days':      total_days_in_month,
        'total_employees': len(result),
        'sheet':           result
    }), 200


# ─────────────────────────────────────────────
# POST /admin/attendance/timesheet/export
# Download timesheet as Excel — one sheet per employee
# ─────────────────────────────────────────────
@admin_bp.route('/admin/attendance/timesheet/export', methods=['POST'])
@admin_required
def export_timesheet_excel():
    month_input = request.form.get('month', '').strip()
    year_input  = request.form.get('year',  '').strip()

    today        = date.today()
    target_month = int(month_input) if month_input else today.month
    target_year  = int(year_input)  if year_input  else today.year

    if not (1 <= target_month <= 12):
        return jsonify({'success': False, 'message': 'month must be between 1 and 12'}), 400

    total_days_in_month = monthrange(target_year, target_month)[1]
    month_name          = date(target_year, target_month, 1).strftime('%B %Y')
    from_date = date(target_year, target_month, 1)
    to_date   = date(target_year, target_month, total_days_in_month)

    employees   = Employee.query.filter_by(active=True).order_by(Employee.created_at.asc()).all()
    all_records = db.session.query(AttendanceRecord).filter(
        AttendanceRecord.date >= from_date,
        AttendanceRecord.date <= to_date
    ).all()

    lookup = {}
    for rec in all_records:
        lookup.setdefault(rec.employee_id, {})[rec.date.day] = rec

    sunday_days   = [d for d in range(1, total_days_in_month + 1)
                     if date(target_year, target_month, d).weekday() == 6]
    db_holidays   = Holiday.query.filter(
        db.extract('year',  Holiday.holiday_date) == target_year,
        db.extract('month', Holiday.holiday_date) == target_month
    ).all()
    holiday_lookup   = {h.holiday_date.day: h.holiday_name for h in db_holidays}
    all_holiday_days = set(sunday_days) | set(holiday_lookup.keys())

    # ── Styles ──
    navy_fill    = PatternFill('solid', start_color='1F3864')
    blue_fill    = PatternFill('solid', start_color='2E75B6')
    green_fill   = PatternFill('solid', start_color='E2EFDA')
    red_fill     = PatternFill('solid', start_color='FCE4D6')
    purple_fill  = PatternFill('solid', start_color='EAD1DC')
    holiday_fill = PatternFill('solid', start_color='D6E4F0')
    grey_fill    = PatternFill('solid', start_color='F2F2F2')
    header_fill  = PatternFill('solid', start_color='DEEAF1')

    def thin_border():
        s = Side(style='thin', color='CCCCCC')
        return Border(left=s, right=s, top=s, bottom=s)

    def cell_style(ws, row, col, value=None, bold=False, color='000000',
                   fill=None, align='center', wrap=False, size=9):
        c = ws.cell(row=row, column=col, value=value)
        c.font      = Font(name='Arial', bold=bold, color=color, size=size)
        c.alignment = Alignment(horizontal=align, vertical='center', wrap_text=wrap)
        c.border    = thin_border()
        if fill:
            c.fill = fill
        return c

    DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    wb = Workbook()
    wb.remove(wb.active)   # remove default blank sheet

    for emp in employees:
        # Sheet name max 31 chars, no special chars
        sheet_name = (emp.name or emp.employee_id)[:28].strip()
        ws = wb.create_sheet(title=sheet_name)
        ws.freeze_panes = 'A7'

        # ── Row 1: Company header ──
        ws.merge_cells('A1:I1')
        c = ws.cell(row=1, column=1, value='ESFITA INFOTECH — Monthly Time Sheet')
        c.font      = Font(name='Arial', bold=True, color='FFFFFF', size=13)
        c.fill      = navy_fill
        c.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 26

        # ── Row 2: Employee month header ──
        ws.merge_cells('A2:I2')
        c = ws.cell(row=2, column=1,
                    value=f"{emp.name}'s Time Sheet for the Month — {month_name}")
        c.font      = Font(name='Arial', bold=True, color='FFFFFF', size=11)
        c.fill      = blue_fill
        c.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[2].height = 22

        # ── Row 3–5: Employee details ──
        detail_font = Font(name='Arial', size=9)
        label_font  = Font(name='Arial', bold=True, size=9)
        for r, (lbl1, val1, lbl2, val2) in enumerate([
            ('Employee Name:',  emp.name or '—',         'Designation:',  emp.designation or '—'),
            ('Employee Phone:', emp.phone or '—',         'Department:',   emp.department  or '—'),
            ('Employee Email:', emp.email or '—',         'Employee ID#:', emp.employee_id or '—'),
        ], start=3):
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=1)
            ws.cell(row=r, column=1, value=lbl1).font = label_font
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
            ws.cell(row=r, column=2, value=val1).font = detail_font
            ws.cell(row=r, column=6, value=lbl2).font = label_font
            ws.merge_cells(start_row=r, start_column=7, end_row=r, end_column=9)
            ws.cell(row=r, column=7, value=val2).font = detail_font
            ws.row_dimensions[r].height = 18

        # ── Row 6: Column headers ──
        col_headers = ['Date', 'Day', 'Module', 'Task Description',
                        'Reg. Hours', 'IN TIME', 'OUT TIME', 'Working Hours', 'Work Location']
        for ci, h in enumerate(col_headers, start=1):
            cell_style(ws, 6, ci, h, bold=True, color='FFFFFF', fill=blue_fill, size=10)
        ws.row_dimensions[6].height = 20

        # ── Column widths ──
        widths = [14, 12, 14, 42, 11, 11, 11, 14, 14]
        for ci, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(ci)].width = w

        # ── Data rows ──
        total_hrs = 0.0
        present = wfh = absent = 0

        for d in range(1, total_days_in_month + 1):
            row     = d + 6
            cur     = date(target_year, target_month, d)
            day_str = DAY_NAMES[cur.weekday()]
            reg_hrs = None if d in sunday_days else 9

            if cur > today:
                row_fill = None
                in_t = out_t = hrs_val = loc = None
                label = None
            elif d in all_holiday_days:
                row_fill = holiday_fill
                in_t = out_t = hrs_val = None
                loc   = holiday_lookup.get(d, 'Sunday / Holiday')
                label = loc
                reg_hrs = None
            elif emp.id in lookup and d in lookup[emp.id]:
                rec = lookup[emp.id][d]
                in_t  = rec.check_in.strftime('%H:%M')  if rec.check_in  else None
                out_t = rec.check_out.strftime('%H:%M') if rec.check_out else None
                hrs_val = None
                if rec.check_in and rec.check_out:
                    hrs_val = round((rec.check_out - rec.check_in).seconds / 3600, 2)
                    total_hrs += hrs_val
                loc = rec.location_type or 'Office'
                label = None
                if loc != 'Office':
                    row_fill = purple_fill
                    wfh += 1
                else:
                    row_fill = green_fill
                    present += 1
            else:
                row_fill = red_fill
                in_t = out_t = hrs_val = None
                loc   = None
                label = 'Absent'
                absent += 1

            task_desc = label or ''
            cell_style(ws, row, 1, cur.strftime('%d-%m-%Y'), fill=row_fill, align='center')
            cell_style(ws, row, 2, day_str,  fill=row_fill, align='center')
            cell_style(ws, row, 3, None,     fill=row_fill, align='center')
            cell_style(ws, row, 4, task_desc, fill=row_fill, align='left', wrap=True)
            cell_style(ws, row, 5, reg_hrs,  fill=row_fill, align='center')
            cell_style(ws, row, 6, in_t,     fill=row_fill, align='center')
            cell_style(ws, row, 7, out_t,    fill=row_fill, align='center')
            cell_style(ws, row, 8, hrs_val,  fill=row_fill, align='center')
            cell_style(ws, row, 9, loc,      fill=row_fill, align='center')
            ws.row_dimensions[row].height = 16

        # ── Summary row ──
        sum_row = total_days_in_month + 7
        ws.merge_cells(start_row=sum_row, start_column=1, end_row=sum_row, end_column=5)
        c = ws.cell(row=sum_row, column=1,
                    value=f'Summary — Present: {present}  WFH: {wfh}  Absent: {absent}  Holidays: {len(all_holiday_days)}  Total Hours: {round(total_hrs, 2)}h')
        c.font      = Font(name='Arial', bold=True, size=9)
        c.fill      = grey_fill
        c.alignment = Alignment(horizontal='left', vertical='center')
        c.border    = thin_border()
        ws.row_dimensions[sum_row].height = 18

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    timestamp = get_ist_now().strftime('%d%m%Y_%H%M%S')
    filename  = f'Timesheet_{month_name.replace(" ", "_")}_{timestamp}.xlsx'

    return send_file(
        buffer,
        as_attachment  = True,
        download_name  = filename,
        mimetype       = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# ─────────────────────────────────────────────
# POST /admin/holidays/add
# ─────────────────────────────────────────────
@admin_bp.route('/admin/holidays/add', methods=['POST'])
@admin_required
def add_holiday():

    holiday_date_str = request.form.get('holiday_date', '').strip()
    holiday_name     = request.form.get('holiday_name', '').strip()

    if not holiday_date_str:
        return jsonify({'success': False, 'message': 'holiday_date is required'}), 400

    if not holiday_name:
        return jsonify({'success': False, 'message': 'holiday_name is required'}), 400

    # ── Parse date ──
    holiday_date = parse_flexible_date(holiday_date_str)
    if not holiday_date:
        return jsonify({
            'success': False,
            'message': 'Invalid date format. Use DD-MM-YYYY'
        }), 400

    # ── Check duplicate ──
    existing = Holiday.query.filter_by(holiday_date=holiday_date).first()
    if existing:
        return jsonify({
            'success': False,
            'message': f'{holiday_date_str} already added as "{existing.holiday_name}"'
        }), 409

    holiday = Holiday(
        holiday_date = holiday_date,
        holiday_name = holiday_name
    )
    db.session.add(holiday)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Holiday "{holiday_name}" added successfully!',
        'holiday': holiday.to_dict()
    }), 201

# ─────────────────────────────────────────────
# GET /admin/holidays
# ─────────────────────────────────────────────
@admin_bp.route('/admin/holidays', methods=['GET'])
@admin_required
def get_holidays():

    year_input = request.args.get('year', '').strip()
    query      = Holiday.query

    if year_input:
        try:
            year  = int(year_input)
            query = query.filter(
                db.extract('year', Holiday.holiday_date) == year
            )
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid year'}), 400

    holidays = query.order_by(Holiday.holiday_date.asc()).all()

    return jsonify({
        'success':  True,
        'count':    len(holidays),
        'holidays': [h.to_dict() for h in holidays]
    }), 200


# ─────────────────────────────────────────────
# DELETE /admin/holidays/<id>
# ─────────────────────────────────────────────
@admin_bp.route('/admin/holidays/<int:holiday_id>', methods=['DELETE'])
@admin_required
def delete_holiday(holiday_id):

    holiday = Holiday.query.get(holiday_id)
    if not holiday:
        return jsonify({'success': False, 'message': 'Holiday not found'}), 404

    name = holiday.holiday_name
    db.session.delete(holiday)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Holiday "{name}" deleted successfully'
    }), 200


@admin_bp.route('/admin/holidays/<int:holiday_id>', methods=['PUT'])
@admin_required
def update_holiday(holiday_id):

    holiday = Holiday.query.get(holiday_id)
    if not holiday:
        return jsonify({
            'success': False,
            'message': 'Holiday not found'
        }), 404

    holiday_date_str = request.form.get('holiday_date', '').strip()
    holiday_name     = request.form.get('holiday_name', '').strip()

    # At least one field should be provided
    if not holiday_date_str and not holiday_name:
        return jsonify({
            'success': False,
            'message': 'Please provide at least holiday_date or holiday_name to update'
        }), 400

    # ── Update Date if provided ──
    if holiday_date_str:
        new_date = parse_flexible_date(holiday_date_str)
        if not new_date:
            return jsonify({
                'success': False,
                'message': 'Invalid date format. Use DD-MM-YYYY'
            }), 400

        # Check if new date already exists (except current holiday)
        existing = Holiday.query.filter(
            Holiday.holiday_date == new_date,
            Holiday.id != holiday_id
        ).first()

        if existing:
            return jsonify({
                'success': False,
                'message': f'Date {holiday_date_str} is already used by "{existing.holiday_name}"'
            }), 409

        holiday.holiday_date = new_date

    # ── Update Name if provided ──
    if holiday_name:
        holiday.holiday_name = holiday_name

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Holiday updated successfully',
        'holiday': holiday.to_dict()
    }), 200


# ─────────────────────────────────────────────
# GET /admin/dashboard          → Summary stats
# ─────────────────────────────────────────────
@admin_bp.route('/admin/dashboard', methods=['GET'])
@admin_required
def dashboard_stats():
    today = date.today()

    total_employees  = Employee.query.filter_by(active=True).count()
    present_today    = AttendanceRecord.query.filter_by(date=today).count()
    absent_today     = total_employees - present_today
    face_registered  = Employee.query.filter_by(face_registered=True).count()
    face_pending     = total_employees - face_registered

    return jsonify({
        'success': True,
        'date': format_date(today),
        'stats': {
            'total_employees': total_employees,
            'present_today':   present_today,
            'absent_today':    absent_today,
            'face_registered': face_registered,
            'face_pending':    face_pending
        }
    }), 200

@admin_bp.route('/admin/create-employee-page')
def create_employee_page():
    return render_template('create_employee.html')