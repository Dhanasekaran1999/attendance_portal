# app/models.py

from app.extensions import db    # ← changed
from datetime import datetime
import bcrypt
import pytz
from app.utils.date_utils import format_date

IST = pytz.timezone('Asia/Kolkata')

def get_ist_now():
    return datetime.now(IST).replace(tzinfo=None)


class Employee(db.Model):
    __tablename__ = 'employees'

    id              = db.Column(db.Integer, primary_key=True)
    employee_id     = db.Column(db.String(50), unique=True, nullable=False)
    name            = db.Column(db.String(100), nullable=False)
    email           = db.Column(db.String(120), unique=True, nullable=False)
    department      = db.Column(db.String(100))
    designation     = db.Column(db.String(100))
    phone           = db.Column(db.String(20))
    password_hash   = db.Column(db.String(256))
    face_encoding   = db.Column(db.ARRAY(db.Float), nullable=True)
    face_registered = db.Column(db.Boolean, default=False)
    active          = db.Column(db.Boolean, default=True)
    admin           = db.Column(db.Boolean, default=False)
    user_type       = db.Column(db.String(20), default='User')
    created_at      = db.Column(db.DateTime, default=get_ist_now)

    attendance_records = db.relationship('AttendanceRecord', backref='employee', lazy=True)
    allowed_locations  = db.relationship('AllowedLocation', backref='employee', lazy=True)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_active(self):
        return self.active

    @property
    def is_admin(self):
        return self.admin

    def get_id(self):
        return str(self.id)

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )

    def to_dict(self):
        return {
            'id':              self.id,
            'employee_id':     self.employee_id,
            'name':            self.name,
            'email':           self.email,
            'department':      self.department,
            'designation':     self.designation,
            'phone':           self.phone,
            'face_registered': self.face_registered,
            'active':          self.active,
            'admin':           self.admin,
            'user_type':       self.user_type,
            'created_at':      self.created_at.isoformat()
        }


class AttendanceRecord(db.Model):
    __tablename__ = 'attendance_records'

    id          = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    check_in    = db.Column(db.DateTime, nullable=True)
    check_out   = db.Column(db.DateTime, nullable=True)
    date        = db.Column(db.Date, default=datetime.utcnow().date)
    status      = db.Column(db.String(20), default='Present')

    login_latitude    = db.Column(db.Float)
    login_longitude   = db.Column(db.Float)
    location          = db.Column(db.String(300), nullable=True)
    location_type = db.Column(db.String(50), nullable=True)
    location_verified = db.Column(db.Boolean, default=False)
    face_verified     = db.Column(db.Boolean, default=False)
    created_at        = db.Column(db.DateTime, default=get_ist_now)

    def to_dict(self):
        return {
            'id':                self.id,
            'employee_id':       self.employee_id,
            'check_in':          self.check_in.isoformat() if self.check_in else None,
            'check_out':         self.check_out.isoformat() if self.check_out else None,
            'date':              format_date(self.date) if self.date else None,
            'status':            self.status,
            'login_latitude':    self.login_latitude,
            'login_longitude':   self.login_longitude,
            'location':          self.location,
            'location_type':     self.location_type,
            'location_verified': self.location_verified,
            'face_verified':     self.face_verified
        }


class AllowedLocation(db.Model):
    __tablename__ = 'allowed_locations'

    id            = db.Column(db.Integer, primary_key=True)
    employee_id   = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    location_type = db.Column(db.String(50), nullable=False)
    location_name = db.Column(db.String(200))
    address       = db.Column(db.String(500), nullable=True)
    latitude      = db.Column(db.Float, nullable=False)
    longitude     = db.Column(db.Float, nullable=False)
    radius_meters = db.Column(db.Integer, default=3000)
    active        = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=get_ist_now)

    def to_dict(self):
        return {
            'id':            self.id,
            'location_type': self.location_type,
            'location_name': self.location_name,
            'address':       self.address,
            'latitude':      self.latitude,
            'longitude':     self.longitude,
            'radius_meters': self.radius_meters,
            'radius_km':     self.radius_meters / 1000,
            'active':        self.active
        }

class OfficeLocation(db.Model):
    __tablename__ = 'office_locations'

    id            = db.Column(db.Integer, primary_key=True)
    office_name   = db.Column(db.String(200), nullable=False)
    address       = db.Column(db.String(500), nullable=False)
    latitude      = db.Column(db.Float, nullable=False)
    longitude     = db.Column(db.Float, nullable=False)
    radius_meters = db.Column(db.Integer, default=3000)
    active        = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=get_ist_now)

    def to_dict(self):
        return {
            'id':            self.id,
            'office_name':   self.office_name,
            'address':       self.address,
            'latitude':      self.latitude,
            'longitude':     self.longitude,
            'radius_meters': self.radius_meters,
            'radius_km':     self.radius_meters / 1000,
            'active':        self.active
        }

class Holiday(db.Model):
    __tablename__ = 'holidays'

    id           = db.Column(db.Integer, primary_key=True)
    holiday_date = db.Column(db.Date, nullable=False, unique=True)
    holiday_name = db.Column(db.String(200), nullable=False)
    created_at   = db.Column(db.DateTime, default=get_ist_now)

    def to_dict(self):
        return {
            'id':           self.id,
            'holiday_date': self.holiday_date.strftime('%d-%m-%Y'),
            'holiday_name': self.holiday_name
        }