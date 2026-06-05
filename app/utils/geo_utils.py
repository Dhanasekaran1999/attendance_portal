# app/utils/geo_utils.py

import math
import requests


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in metres between two GPS points."""
    R = 6371000  # Earth radius in metres

    phi1         = math.radians(lat1)
    phi2         = math.radians(lat2)
    delta_phi    = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) *
         math.sin(delta_lambda / 2) ** 2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def is_within_allowed_locations(user_lat, user_lon, allowed_locations, office_locations=None):
    """
    Check if user is within ANY allowed location OR any office location.
    """

    all_locations  = []
    closest_location = None
    closest_distance = float('inf')

    # ── Check office locations first (global for all employees) ──
    if office_locations:
        for office in office_locations:
            distance    = haversine_distance(user_lat, user_lon, office.latitude, office.longitude)
            distance_km = round(distance / 1000, 2)

            if distance < closest_distance:
                closest_distance = distance
                closest_location = office

            if distance <= office.radius_meters:
                return True, office, distance_km, \
                       f"Location verified! You are at {office.office_name} ({distance_km}km)"

    # ── Check employee personal locations (Home/Hostel/Other) ──
    if allowed_locations:
        for location in allowed_locations:
            distance    = haversine_distance(user_lat, user_lon, location.latitude, location.longitude)
            distance_km = round(distance / 1000, 2)

            if distance < closest_distance:
                closest_distance = distance
                closest_location = location

            if distance <= location.radius_meters:
                return True, location, distance_km, \
                       f"Location verified! You are at {location.location_name} ({distance_km}km)"

    # ── Not within any location ──
    if not closest_location:
        return False, None, 0, \
               "No allowed locations set for this employee. Contact admin."

    closest_km   = round(closest_distance / 1000, 2)
    location_name = getattr(closest_location, 'office_name', None) or \
                    getattr(closest_location, 'location_name', None)

    return False, closest_location, closest_km, \
           f"Access denied. You are {closest_km}km away from nearest location ({location_name})."


def get_location_name(lat, lon):
    """
    Convert lat/lon to most detailed readable address.
    """
    try:
        url     = "https://nominatim.openstreetmap.org/reverse"
        params  = {
            'lat':            lat,
            'lon':            lon,
            'format':         'json',
            'addressdetails': 1,
            'zoom':           18
        }
        headers = {'User-Agent': 'AttendancePortal/1.0'}

        response = requests.get(
            url, params=params, headers=headers, timeout=5
        )
        data = response.json()

        if 'address' in data:
            address = data.get('address', {})

            parts = []

            # ── Collect all available detailed parts ──
            for key in [
                'house_number',
                'road',
                'neighbourhood',
                'suburb',
                'village',
                'county',
                'city_district',
                'city',
                'town',
                'municipality',
                'state_district',
                'state'
            ]:
                value = address.get(key)
                if value and value not in parts:
                    parts.append(value)

            if parts:
                return ', '.join(parts)

            # ── Final fallback — use full display_name ──
            return data.get('display_name', f"{lat},{lon}")

        return f"{lat}, {lon}"

    except Exception:
        return f"{lat}, {lon}"

def _try_geocode(address, headers):
    """Try to geocode an address. Returns results list or empty list."""
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params  = {'q': address, 'format': 'json', 'limit': 1},
            headers = headers,
            timeout = 5
        )
        return response.json()
    except Exception:
        return []