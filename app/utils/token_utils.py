import jwt
import pytz
from datetime import datetime, timedelta
from flask import request, jsonify, current_app
from functools import wraps

IST = pytz.timezone('Asia/Kolkata')

def get_ist_now():
    return datetime.now(IST).replace(tzinfo=None)


def generate_token(employee_id, user_type, is_admin):
    """Generate JWT token using IST time."""

    now    = datetime.now(pytz.utc)   # ← JWT always needs UTC for exp/iat
    expiry = now + timedelta(
        minutes=current_app.config['JWT_EXPIRY_MINUTES']
    )

    payload = {
        'employee_id': employee_id,
        'user_type':   user_type,
        'is_admin':    is_admin,
        'iat':         now,            # ← UTC datetime object (not utctimetuple)
        'exp':         expiry          # ← UTC datetime object
    }

    token = jwt.encode(
        payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )

    return token


def decode_token(token):
    """Decode and verify JWT token."""
    payload = jwt.decode(
        token,
        current_app.config['JWT_SECRET_KEY'],
        algorithms=['HS256']
    )
    return payload


# ─────────────────────────────────────────────
# Decorator — Any logged-in user
# ─────────────────────────────────────────────
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        if not token:
            return jsonify({
                'success': False,
                'message': 'Token is missing. Please login first.'
            }), 401

        try:
            payload = decode_token(token)
            request.current_employee_id = payload['employee_id']
            request.current_user_type   = payload['user_type']
            request.current_is_admin    = payload['is_admin']

        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'message': 'Token has expired. Please login again.'
            }), 401

        except jwt.InvalidTokenError:
            return jsonify({
                'success': False,
                'message': 'Invalid token. Please login again.'
            }), 401

        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# Decorator — Admin only
# ─────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        if not token:
            return jsonify({
                'success': False,
                'message': 'Token is missing. Please login first.'
            }), 401

        try:
            payload = decode_token(token)
            request.current_employee_id = payload['employee_id']
            request.current_user_type   = payload['user_type']
            request.current_is_admin    = payload['is_admin']

        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'message': 'Token has expired. Please login again.'
            }), 401

        except jwt.InvalidTokenError:
            return jsonify({
                'success': False,
                'message': 'Invalid token. Please login again.'
            }), 401

        if not payload.get('is_admin'):
            return jsonify({
                'success': False,
                'message': 'Access denied. Admin only.'
            }), 403

        return f(*args, **kwargs)
    return decorated