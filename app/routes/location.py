# app/routes/location.py

from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models import Employee, AllowedLocation, OfficeLocation
from app.utils.token_utils import admin_required, token_required
from datetime import datetime
import pytz
from app.utils.geo_utils import _try_geocode

IST = pytz.timezone('Asia/Kolkata')
def get_ist_now():
    return datetime.now(IST).replace(tzinfo=None)

location_bp = Blueprint('location', __name__)

# POST /admin/locations/add
# Admin adds allowed location for an employee
# ─────────────────────────────────────────────
@location_bp.route('/admin/locations/add', methods=['POST'])
@admin_required
def add_location():
    import requests

    employee_id   = request.form.get('employee_id', '').strip()
    location_type = request.form.get('location_type', '').strip()
    location_name = request.form.get('location_name', '').strip()
    address       = request.form.get('address', '').strip()
    radius_meters = request.form.get('radius_meters', '3000').strip()
    manual_lat    = request.form.get('latitude', '').strip()   # ← optional
    manual_lon    = request.form.get('longitude', '').strip()  # ← optional

    # ── Validate required fields ──
    if not employee_id:
        return jsonify({'success': False, 'message': 'employee_id is required'}), 400

    if not location_type:
        return jsonify({'success': False, 'message': 'location_type is required'}), 400

    if not location_name:
        return jsonify({'success': False, 'message': 'location_name is required'}), 400

    if not address:
        return jsonify({'success': False, 'message': 'address is required'}), 400

    # ── Validate location_type ──
    valid_types = ['Home', 'Hostel', 'Other']
    if location_type not in valid_types:
        return jsonify({
            'success': False,
            'message': f'location_type must be one of: {", ".join(valid_types)}'
        }), 400

    # ── Validate radius ──
    try:
        radius = int(radius_meters)
        if radius < 100 or radius > 50000:
            return jsonify({
                'success': False,
                'message': 'radius_meters must be between 100 and 50000'
            }), 400
    except ValueError:
        return jsonify({'success': False, 'message': 'radius_meters must be a valid number'}), 400

    # ── Find employee ──
    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({'success': False, 'message': f'Employee {employee_id} not found'}), 404

    # ── Check max 3 locations ──
    existing_count = AllowedLocation.query.filter_by(
        employee_id=emp.id
    ).count()

    if existing_count >= 3:
        return jsonify({
            'success': False,
            'message': f'{emp.name} already has 3 allowed locations. Delete one before adding.'
        }), 400

    # ── Check duplicate location_type ──
    duplicate = AllowedLocation.query.filter_by(
        employee_id   = emp.id,
        location_type = location_type
    ).first()

    if duplicate:
        return jsonify({
            'success': False,
            'message': f'{emp.name} already has a {location_type} location. Edit or delete it first.'
        }), 409

    # ── Get coordinates ──
    coord_source = ''

    if manual_lat and manual_lon:
        # ── Option A: Use manually provided coordinates ──
        try:
            lat = round(float(manual_lat), 4)
            lon = round(float(manual_lon), 4)
            coord_source = 'manual'
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid latitude or longitude value.'
            }), 400

    else:
        # ── Option B: Auto fetch from address ──
        try:
            headers  = {'User-Agent': 'AttendancePortal/1.0'}

            # Try 1 — full address
            results = _try_geocode(address, headers)

            # Try 2 — remove PIN code
            if not results:
                import re
                cleaned = re.sub(r'-?\d{6}', '', address).strip().strip(',').strip()
                results = _try_geocode(cleaned, headers)

            # Try 3 — last two parts only
            if not results:
                parts   = [p.strip() for p in address.split(',') if p.strip()]
                short   = ', '.join(parts[-2:])
                results = _try_geocode(short, headers)

            if not results:
                return jsonify({
                    'success': False,
                    'message': f'Could not auto-fetch coordinates for: "{address}". '
                               f'Please provide latitude and longitude manually.'
                }), 400

            lat = round(float(results[0]['lat']), 4)
            lon = round(float(results[0]['lon']), 4)
            coord_source = 'auto'

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error fetching coordinates: {str(e)}'
            }), 500

    # ── Save location ──
    loc = AllowedLocation(
        employee_id   = emp.id,
        location_type = location_type,
        location_name = location_name,
        address       = address,
        latitude      = lat,
        longitude     = lon,
        radius_meters = radius
    )
    db.session.add(loc)
    db.session.commit()

    total_locations = AllowedLocation.query.filter_by(employee_id=emp.id).count()

    return jsonify({
        'success':      True,
        'message':      f'{location_type} location added for {emp.name}!',
        'coord_source': coord_source,  # 'manual' or 'auto'
        'location': {
            'sno': total_locations,
            'id':            loc.id,
            'employee_id':   emp.employee_id,
            'employee_name': emp.name,
            'location_type': loc.location_type,
            'location_name': loc.location_name,
            'address':       loc.address,
            'latitude':      loc.latitude,
            'longitude':     loc.longitude,
            'radius_meters': loc.radius_meters,
            'radius_km':     loc.radius_meters / 1000
        }
    }), 201


# ─────────────────────────────────────────────
# GET /admin/locations/<employee_id>
# Get all allowed locations for an employee
# ─────────────────────────────────────────────
@location_bp.route('/admin/locations/<string:employee_id>', methods=['GET'])
@admin_required
def get_locations(employee_id):

    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404

    locations = AllowedLocation.query.filter_by(
        employee_id = emp.id
    ).all()

    result = []
    for idx, loc in enumerate(locations, start=1):
        data        = loc.to_dict()
        data['sno'] = idx
        result.append(data)

    return jsonify({
        'success':       True,
        'employee_id':   emp.employee_id,
        'employee_name': emp.name,
        'total':         len(result),
        'locations':     result
    }), 200


# ─────────────────────────────────────────────
# PUT /admin/locations/<location_id>/edit
# Edit an allowed location
# ─────────────────────────────────────────────
@location_bp.route('/admin/locations/<int:location_id>/edit', methods=['PUT'])
@admin_required
def edit_location(location_id):

    loc = AllowedLocation.query.get(location_id)
    if not loc:
        return jsonify({'success': False, 'message': 'Location not found'}), 404

    location_name = request.form.get('location_name', '').strip()
    latitude      = request.form.get('latitude', '').strip()
    longitude     = request.form.get('longitude', '').strip()
    radius_meters = request.form.get('radius_meters', '').strip()
    address       = request.form.get('address', '').strip()  # ← manual address

    updated = []

    if location_name:
        loc.location_name = location_name
        updated.append('location_name')

    if address:
        loc.address = address          # ← save manual address directly
        updated.append('address')

    if latitude and longitude:
        try:
            loc.latitude = round(float(latitude), 4)
            loc.longitude = round(float(longitude), 4)
            updated.append('coordinates')
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid coordinates'}), 400

    if radius_meters:
        try:
            radius = int(radius_meters)
            if radius < 100 or radius > 50000:
                return jsonify({'success': False, 'message': 'radius_meters must be between 100 and 50000'}), 400
            loc.radius_meters = radius
            updated.append('radius_meters')
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid radius'}), 400

    if not updated:
        return jsonify({'success': False, 'message': 'No fields to update'}), 400

    db.session.commit()

    return jsonify({
        'success':        True,
        'message':        'Location updated successfully',
        'updated_fields': updated,
        'location':       loc.to_dict()
    }), 200


# ─────────────────────────────────────────────
# DELETE /admin/locations/<location_id>
# Delete an allowed location
# ─────────────────────────────────────────────
@location_bp.route('/admin/locations/<int:location_id>', methods=['DELETE'])
@admin_required
def delete_location(location_id):

    loc = AllowedLocation.query.get(location_id)
    if not loc:
        return jsonify({'success': False, 'message': 'Location not found'}), 404

    location_type = loc.location_type  # save before deleting

    db.session.delete(loc)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'{location_type} location permanently deleted'
    }), 200


# ─────────────────────────────────────────────
# GET /api/my-locations
# Employee views their own allowed locations
# ─────────────────────────────────────────────
@location_bp.route('/api/my-locations', methods=['GET'])
@token_required
def my_locations():

    employee_id = request.args.get('employee_id', '').strip()

    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404

    locations = AllowedLocation.query.filter_by(
        employee_id = emp.id,
        active      = True
    ).all()

    return jsonify({
        'success':   True,
        'employee':  emp.name,
        'locations': [loc.to_dict() for loc in locations]
    }), 200


@location_bp.route('/admin/office-location/add', methods=['POST'])
@admin_required
def add_office_location():

    office_name   = request.form.get('office_name', '').strip()
    address       = request.form.get('address', '').strip()
    radius_meters = request.form.get('radius_meters', '3000').strip()
    manual_lat    = request.form.get('latitude', '').strip()
    manual_lon    = request.form.get('longitude', '').strip()

    # ── Validate ──
    if not office_name:
        return jsonify({'success': False, 'message': 'office_name is required'}), 400

    if not address:
        return jsonify({'success': False, 'message': 'address is required'}), 400

    # ── Only ONE office location allowed ──
    existing = OfficeLocation.query.first()
    if existing:
        return jsonify({
            'success': False,
            'message': f'Office location already exists: "{existing.office_name}". Use edit API to update it.',
            'existing_office': existing.to_dict()
        }), 409

    # ── Validate radius ──
    try:
        radius = int(radius_meters)
        if radius < 100 or radius > 50000:
            return jsonify({'success': False,
                            'message': 'radius_meters must be between 100 and 50000'}), 400
    except ValueError:
        return jsonify({'success': False, 'message': 'radius_meters must be a valid number'}), 400

    # ── Get coordinates ──
    if manual_lat and manual_lon:
        try:
            lat = round(float(manual_lat), 4)
            lon = round(float(manual_lon), 4)
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid latitude or longitude'}), 400
    else:
        import requests
        headers = {'User-Agent': 'AttendancePortal/1.0'}
        results = _try_geocode(address, headers)
        if not results:
            return jsonify({
                'success': False,
                'message': 'Could not auto-fetch coordinates. Please provide latitude and longitude manually.'
            }), 400
        lat = round(float(results[0]['lat']), 4)
        lon = round(float(results[0]['lon']), 4)

    # ── Save office location ──
    office = OfficeLocation(
        office_name   = office_name,
        address       = address,
        latitude      = lat,
        longitude     = lon,
        radius_meters = radius,
        active        = True
    )
    db.session.add(office)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Office location "{office_name}" added successfully!',
        'office':  office.to_dict()
    }), 201


# ─────────────────────────────────────────────
# GET /admin/office-location
# Get all office locations
# ─────────────────────────────────────────────
@location_bp.route('/admin/office-location', methods=['GET'])
@admin_required
def get_office_locations():

    offices = OfficeLocation.query.filter_by(active=True).all()

    return jsonify({
        'success': True,
        'count':   len(offices),
        'offices': [o.to_dict() for o in offices]
    }), 200


# ─────────────────────────────────────────────
# PUT /admin/office-location/<id>/edit
# Edit office location
# ─────────────────────────────────────────────
@location_bp.route('/admin/office-location/<int:office_id>/edit', methods=['PUT'])
@admin_required
def edit_office_location(office_id):

    office = OfficeLocation.query.get(office_id)
    if not office:
        return jsonify({'success': False, 'message': 'Office location not found'}), 404

    office_name   = request.form.get('office_name', '').strip()
    address       = request.form.get('address', '').strip()
    latitude      = request.form.get('latitude', '').strip()
    longitude     = request.form.get('longitude', '').strip()
    radius_meters = request.form.get('radius_meters', '').strip()

    updated = []

    if office_name:
        office.office_name = office_name
        updated.append('office_name')

    if address:
        office.address = address
        updated.append('address')

    if latitude and longitude:
        try:
            office.latitude = round(float(latitude), 4)
            office.longitude = round(float(longitude), 4)
            updated.append('coordinates')
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid coordinates'}), 400

    if radius_meters:
        try:
            radius = int(radius_meters)
            if radius < 100 or radius > 50000:
                return jsonify({'success': False,
                                'message': 'radius_meters must be between 100 and 50000'}), 400
            office.radius_meters = radius
            updated.append('radius_meters')
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid radius'}), 400

    if not updated:
        return jsonify({'success': False, 'message': 'No fields to update'}), 400

    db.session.commit()

    return jsonify({
        'success':        True,
        'message':        'Office location updated successfully',
        'updated_fields': updated,
        'office':         office.to_dict()
    }), 200


# ─────────────────────────────────────────────
# DELETE /admin/office-location/<id>
# Delete office location
# ─────────────────────────────────────────────
@location_bp.route('/admin/office-location/<int:office_id>', methods=['DELETE'])
@admin_required
def delete_office_location(office_id):

    office = OfficeLocation.query.get(office_id)
    if not office:
        return jsonify({'success': False, 'message': 'Office location not found'}), 404

    db.session.delete(office)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Office location "{office.office_name}" deleted successfully'
    }), 200
