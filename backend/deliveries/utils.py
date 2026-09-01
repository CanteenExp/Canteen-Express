import math

# Palawan State University Main Campus (Tiniguiban Heights, Puerto Princesa) -
# delivery scope is campus only.
# Official Main Campus center (9.77778, 118.73333 per Wikipedia/Wikidata).
CAMPUS_CENTER_LAT = 9.77778
CAMPUS_CENTER_LNG = 118.73333
# Maximum distance from campus center that is still considered "on campus".
# 0.8 km covers the ~68 hectare main campus and its buildings.
CAMPUS_RADIUS_KM = 0.8


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance between two coordinates in kilometers."""
    if lat1 is None or lng1 is None or lat2 is None or lng2 is None:
        return 0.0
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def is_within_campus(lat, lng):
    """True if the coordinates fall inside the campus geofence."""
    if lat is None or lng is None:
        return False
    return haversine_km(lat, lng, CAMPUS_CENTER_LAT, CAMPUS_CENTER_LNG) <= CAMPUS_RADIUS_KM


def distance_from_points(points):
    """Sum of haversine distances (km) across an ordered list of (lat, lng) tuples."""
    total = 0.0
    for i in range(1, len(points)):
        total += haversine_km(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])
    return total


def compute_speed_kmh(lat1, lng1, t1, lat2, lng2, t2):
    """Speed between two points given their timestamps (seconds). Returns km/h."""
    if lat1 is None or lat2 is None:
        return 0.0
    if t1 is None or t2 is None:
        return 0.0
    dt_sec = (t2 - t1).total_seconds()
    if dt_sec <= 0:
        return 0.0
    d_km = haversine_km(lat1, lng1, lat2, lng2)
    return (d_km / dt_sec) * 3600.0


def compute_bearing(lat1, lng1, lat2, lng2):
    """Initial bearing (heading) in degrees from point1 to point2 (0-360, clockwise from North)."""
    if lat1 is None or lng1 is None or lat2 is None or lng2 is None:
        return None
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lng2 - lng1)
    lat1r = math.radians(lat1)
    lat2r = math.radians(lat2)
    y = math.sin(dlon) * math.cos(lat2r)
    x = (math.cos(lat1r) * math.sin(lat2r)
         - math.sin(lat1r) * math.cos(lat2r) * math.cos(dlon))
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360
