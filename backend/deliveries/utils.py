import math

from django.db.models import Case, When, Value, IntegerField
from django.utils import timezone

from .models import DeliveryRequest


def pending_pool_for_rider(user):
    """SEARCHING deliveries visible to a rider -- every proposal in the shared
    pool. There is no pre-assigned rider until one accepts: whoever taps Accept
    first claims the order (atomic guard in accept_delivery).

    Ordered FIFO by how long each order has been waiting so the queue stays
    fair: the longest-waiting delivery is the one riders see first. pool_rank
    still surfaces any legacy assigned_to offer to that rider first without
    hiding the rest of the pool."""
    return (DeliveryRequest.objects
            .filter(status=DeliveryRequest.RequestStatus.SEARCHING)
            .annotate(
                pool_rank=Case(
                    When(assigned_to=user, then=Value(0)),
                    When(assigned_to__isnull=True, then=Value(1)),
                    default=Value(2),
                    output_field=IntegerField(),
                )
            )
            .order_by('pool_rank', 'requested_at'))


def _clean_amount(amount):
    """Return a float rounded to 2 decimals (peso-cents) to avoid float drift."""
    import math
    if amount is None:
        return 0.0
    return round(float(amount), 2)


def delivery_fee_for_order(total_amount):
    """Delivery fee / rider earning: ₱15 base fee per order, +₱15 per ₱300 block.

    The ₱15 base covers the 0-300 range, then +₱15 for each additional ₱300:
    ₱0-300 -> ₱15, ₱300.01-600 -> ₱30, ₱600.01-900 -> ₱45, etc.

    Uses a tiny epsilon so a float-summed subtotal of exactly ₱300.00 is never
    bumped into the ₱30 bracket by rounding noise.
    """
    import math
    amount = _clean_amount(total_amount)
    if amount is None:
        return 15.0
    if amount <= 0:
        return 15.0
    return float(max(15, math.ceil((amount - 1e-6) / 300) * 15))


# Keep old name as alias for backward compat
delivery_earning_for_order = delivery_fee_for_order


def serialize_delivery(d):
    """Shared serializer for a DeliveryRequest shown to the faculty customer side.

    Includes the rider's live position so a single faculty SSE payload carries
    both the order status and the rider's real-time GPS location.
    """
    return {
        'id': d.id,
        'order_number': d.order.order_number,
        'status': d.get_status_display(),
        'raw_status': d.status,
        'location': d.delivery_location,
        'rider_name': d.rider.get_full_name() or d.rider.username if d.rider else 'Searching for Rider...',
        'assigned_rider_name': (d.assigned_to.get_full_name() or d.assigned_to.username
                                if d.assigned_to else None),
        'total_amount': float(d.order.total_amount),
        'delivery_fee': float(d.order.delivery_fee),
        'total_payment': float(d.order.total_amount) + float(d.order.delivery_fee),
        'customer_name': d.order.customer.get_full_name() or d.order.customer.username if d.order.customer else 'Guest',
        'created_at': d.requested_at.strftime('%H:%M %p'),
        'rider_lat': d.rider_lat,
        'rider_lng': d.rider_lng,
        'dest_lat': d.dest_lat,
        'dest_lng': d.dest_lng,
        'location_updated_at': d.location_updated_at.strftime('%H:%M %p') if d.location_updated_at else None,
        'items': [{'name': i.item_name, 'qty': i.quantity, 'price': float(i.price)} for i in d.order.items.all()]
    }


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
