# app/routes/auth.py

import base64
from flask import Blueprint, request, jsonify, render_template
from app.extensions import db
from app.models import Employee, AttendanceRecord, AllowedLocation, OfficeLocation
from app.utils.face_utils import extract_face_encoding, verify_face
from app.utils.geo_utils import is_within_allowed_locations, get_location_name
from datetime import datetime, date
import pytz
from app.utils.token_utils import token_required
from app.utils.token_utils import generate_token

IST = pytz.timezone('Asia/Kolkata')

def get_ist_now():
    return datetime.now(IST).replace(tzinfo=None)  # naive datetime for DB

auth_bp = Blueprint('auth', __name__)

from app import login_manager

@login_manager.user_loader
def load_user(user_id):
    return Employee.query.get(int(user_id))


# ─────────────────────────────────────────────
# POST /api/register-face  → form-data
# ─────────────────────────────────────────────
@auth_bp.route('/api/register-face', methods=['POST'])
def register_face():

    # ── Get employee_id from form ──
    employee_id = request.form.get('employee_id')
    if not employee_id:
        return jsonify({
            'success': False,
            'message': 'employee_id is required'
        }), 400

    # ── Get image file from form ──
    if 'face_image' not in request.files:
        return jsonify({
            'success': False,
            'message': 'face_image file is required'
        }), 400

    file = request.files['face_image']

    if file.filename == '':
        return jsonify({
            'success': False,
            'message': 'No file selected'
        }), 400

    # ── Convert uploaded file to base64 ──
    file_bytes    = file.read()
    base64_string = base64.b64encode(file_bytes).decode('utf-8')
    face_image    = f"data:image/jpeg;base64,{base64_string}"

    # ── Find employee ──
    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({
            'success': False,
            'message': f'Employee {employee_id} not found'
        }), 404

    if not emp.active:
        return jsonify({
            'success': False,
            'message': 'Employee account is inactive. Contact admin.'
        }), 403

    # ── Already registered? ──
    if emp.face_registered:
        return jsonify({
            'success':         False,
            'message':         f'Face already registered for {emp.name}. Use /api/update-face to update.',
            'face_registered': True
        }), 400

    # ── Extract face encoding ──
    encoding, message = extract_face_encoding(face_image)
    if encoding is None:
        return jsonify({
            'success': False,
            'message': message
        }), 400

    # ── Save to database ──
    emp.face_encoding   = encoding
    emp.face_registered = True
    db.session.commit()

    return jsonify({
        'success':         True,
        'message':         f'Face registered successfully for {emp.name}!',
        'employee_id':     emp.employee_id,
        'employee_name':   emp.name,
        'face_registered': True,
        'encoding_length': len(encoding)
    }), 200


# ─────────────────────────────────────────────
# POST /api/update-face  → form-data
# ─────────────────────────────────────────────
@auth_bp.route('/api/update-face', methods=['POST'])
def update_face():

    employee_id = request.form.get('employee_id')
    if not employee_id:
        return jsonify({'success': False, 'message': 'employee_id is required'}), 400

    if 'face_image' not in request.files:
        return jsonify({'success': False, 'message': 'face_image file is required'}), 400

    file          = request.files['face_image']
    file_bytes    = file.read()
    base64_string = base64.b64encode(file_bytes).decode('utf-8')
    face_image    = f"data:image/jpeg;base64,{base64_string}"

    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404

    encoding, message = extract_face_encoding(face_image)
    if encoding is None:
        return jsonify({'success': False, 'message': message}), 400

    emp.face_encoding   = encoding
    emp.face_registered = True
    db.session.commit()

    return jsonify({
        'success':         True,
        'message':         f'Face updated successfully for {emp.name}!',
        'employee_id':     emp.employee_id,
        'face_registered': True
    }), 200


# ─────────────────────────────────────────────
# GET /api/face-status/<employee_id>
# ─────────────────────────────────────────────
@auth_bp.route('/api/face-status/<string:employee_id>', methods=['GET'])
def face_status(employee_id):
    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404

    return jsonify({
        'success':         True,
        'employee_id':     emp.employee_id,
        'employee_name':   emp.name,
        'face_registered': emp.face_registered,
        'message':         'Face is registered. Ready to login.'
                           if emp.face_registered else 'Face not registered yet.'
    }), 200

# POST /api/login
# Login with employee_id + password
# ─────────────────────────────────────────────

@auth_bp.route('/api/login', methods=['POST'])
def login():

    employee_id = request.form.get('employee_id', '').strip()
    password    = request.form.get('password', '').strip()

    if not employee_id or not password:
        return jsonify({
            'success': False,
            'message': 'employee_id and password are required'
        }), 400

    emp = Employee.query.filter_by(employee_id=employee_id).first()

    if not emp:
        return jsonify({
            'success': False,
            'message': 'Invalid employee ID or password'
        }), 401

    if not emp.active:
        return jsonify({
            'success': False,
            'message': 'Your account has been deactivated. Contact admin.'
        }), 403

    if not emp.check_password(password):
        return jsonify({
            'success': False,
            'message': 'Invalid employee ID or password'
        }), 401

    # ── Generate token ──
    token = generate_token(
        employee_id = emp.employee_id,
        user_type   = emp.user_type,
        is_admin    = emp.admin
    )

    # ── IST login time ──
    login_time = get_ist_now().strftime('%Y-%m-%d %H:%M:%S')

    return jsonify({
        'success':         True,
        'message':         f'Welcome, {emp.name}!',
        'token':           token,
        'token_type':      'Bearer',
        'expires_in':      '24 hours',
        'login_time':      login_time,           # ← IST time
        'employee_id':     emp.employee_id,
        'name':            emp.name,
        'email':           emp.email,
        'department':      emp.department,
        'designation':     emp.designation,
        'phone':           emp.phone,
        'user_type':       emp.user_type,
        'is_admin':        emp.admin,
        'face_registered': emp.face_registered,
        'next_step':       'register_face' if not emp.face_registered else 'attendance'
    }), 200

# ─────────────────────────────────────────────
# POST /api/change-password
# Employee changes their own password
# ─────────────────────────────────────────────
@auth_bp.route('/api/change-password', methods=['POST'])
@token_required
def change_own_password():

    employee_id  = request.form.get('employee_id', '').strip()
    old_password = request.form.get('old_password', '').strip()
    new_password = request.form.get('new_password', '').strip()

    # ── Validate required fields ──
    if not all([employee_id, old_password, new_password]):
        return jsonify({
            'success': False,
            'message': 'employee_id, old_password and new_password are required'
        }), 400

    # ── Validate password length ──
    if len(new_password) < 6:
        return jsonify({
            'success': False,
            'message': 'New password must be at least 6 characters.'
        }), 400

    # ── Find employee ──
    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({
            'success': False,
            'message': 'Employee not found'
        }), 404

    # ── Check old password ──
    if not emp.check_password(old_password):
        return jsonify({
            'success': False,
            'message': 'Old password is incorrect'
        }), 401

    # ── Old and new same ──
    if old_password == new_password:
        return jsonify({
            'success': False,
            'message': 'New password must be different from old password.'
        }), 400

    # ── Save new password ──
    emp.set_password(new_password)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Password changed successfully!'
    }), 200


@auth_bp.route('/api/face-login', methods=['POST'])
def face_login():

    latitude  = request.form.get('latitude')
    longitude = request.form.get('longitude')

    # ── Validate face image ──
    if 'face_image' not in request.files:
        return jsonify({'success': False, 'message': 'face_image is required'}), 400

    file          = request.files['face_image']
    file_bytes    = file.read()
    base64_string = base64.b64encode(file_bytes).decode('utf-8')
    face_image    = f"data:image/jpeg;base64,{base64_string}"

    if not latitude or not longitude:
        return jsonify({
            'success': False,
            'message': 'Location not detected. Please allow location access.'
        }), 400

    # ── Get ALL active employees with registered faces ──
    employees = Employee.query.filter_by(
        active=True, face_registered=True
    ).all()

    if not employees:
        return jsonify({
            'success': False,
            'message': 'No registered faces found in system.'
        }), 404

    # ── Get office locations ──
    office_locations  = OfficeLocation.query.filter_by(active=True).all()

    # ── Scan face against ALL employees ──
    best_match      = None
    best_confidence = 0.0

    for emp in employees:
        if not emp.face_encoding:
            continue
        face_match, confidence, _ = verify_face(
            face_image, emp.face_encoding
        )
        if face_match and confidence > best_confidence:
            best_match      = emp
            best_confidence = confidence

    # ── No match found ──
    if not best_match:
        return jsonify({
            'success':    False,
            'message':    'Face not recognized. Please try again.',
            'confidence': 0.0
        }), 401

    emp = best_match

    # ── Get employee personal locations ──
    allowed_locations = AllowedLocation.query.filter_by(
        employee_id=emp.id
    ).all()

    # ── Location check ──
    location_ok, matched_location, distance_km, loc_message = is_within_allowed_locations(
        float(latitude), float(longitude),
        allowed_locations,
        office_locations
    )

    if not location_ok:
        return jsonify({
            'success':  False,
            'message':  loc_message,
            'distance': f'{distance_km}km'
        }), 403

    # ── Get readable location name ──
    location_name = get_location_name(float(latitude), float(longitude))

    # ── Get location type ──
    matched_type = getattr(matched_location, 'location_type', None) or 'Office'

    # ── Record attendance ──
    today    = date.today()
    existing = AttendanceRecord.query.filter_by(
        employee_id=emp.id, date=today
    ).first()

    now    = get_ist_now()
    action = ''

    if not existing:
        record       = AttendanceRecord(
            employee_id       = emp.id,
            check_in          = now,
            date              = today,
            status            = 'Present',
            login_latitude    = float(latitude),
            login_longitude   = float(longitude),
            location          = location_name,
            location_type     = matched_type,
            location_verified = True,
            face_verified     = True
        )
        db.session.add(record)
        action = 'check_in'

    elif existing.check_in and not existing.check_out:
        existing.check_out = now
        action             = 'check_out'

    else:
        action = 'already_completed'

    db.session.commit()

    # ── Calculate hours worked ──
    hours_worked = None
    if action == 'check_out' and existing.check_in:
        seconds      = (now - existing.check_in).seconds
        hours_worked = round(seconds / 3600, 2)

    matched_name = getattr(matched_location, 'office_name', None) or \
                   getattr(matched_location, 'location_name', None)

    return jsonify({
        'success':      True,
        'message':      f'Welcome, {emp.name}!',
        'action':       action,
        'confidence':   best_confidence,
        'location':     location_name,
        'location_type': matched_type,
        'distance':     f'{distance_km}km from {matched_name}',
        'time':         now.strftime('%d-%m-%Y %H:%M:%S'),
        'hours_worked': hours_worked,
        'employee': {
            'employee_id': emp.employee_id,
            'name':        emp.name,
            'designation': emp.designation,
            'department':  emp.department,
            'email':       emp.email,
            'phone':       emp.phone,
            'user_type':   emp.user_type
        }
    }), 200

# ─────────────────────────────────────────────
# GET /
# ─────────────────────────────────────────────
@auth_bp.route('/')
def index():
    return jsonify({
        'message': 'Attendance Portal API is running!',
        'endpoints': [
            'POST /api/register-face  (form-data)',
            'POST /api/update-face    (form-data)',
            'GET  /api/face-status/<employee_id>',
            'POST /api/face-login     (form-data)',
        ]
    }), 200


# Serve the register face HTML page
@auth_bp.route('/register-face-page')
def register_face_page():
    return render_template('register_face.html')

@auth_bp.route('/face-login-page')
def face_login_page():
    return render_template('face_login.html')

@auth_bp.route('/login-page')
def login_page():
    return render_template('login.html')

@auth_bp.route('/attendance')
def attendance_page():
    return render_template('attendance.html')