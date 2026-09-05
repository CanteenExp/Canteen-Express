import math

from django.db.models import Count, Q, Case, When, Value, IntegerField
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import DeliveryRequest


def pick_next_available_rider(exclude_id=None):
    """Round-robin: pick the online DELIVERY rider with the fewest active
    deliveries (most idle) to receive the next order. Ties broken by the
    earliest availability-update / earliest join (oldest first). Excludes an
    optional rider id (used when rotating away from a declining rider).

    Returns a CustomUser for a rider, or None if no online rider is available.
    """
    User = get_user_model()
    MAX_ACTIVE = 3

    online = User.objects.filter(
        role='DELIVERY',
        is_available=True,
        account_status='active',
    )
    if exclude_id:
        online = online.exclude(id=exclude_id)

    # Annotate with the rider's current active (ACCEPTED) delivery count.
    active_counts = (
        DeliveryRequest.objects
        .filter(status=DeliveryRequest.RequestStatus.ACCEPTED)
        .values('rider_id')
        .annotate(cnt=Count('id'))
    )
    count_map = {c['rider_id']: c['cnt'] for c in active_counts}

    candidates = [
        r for r in online
        if count_map.get(r.id, 0) < MAX_ACTIVE
    ]

    if not candidates:
        return None

    # Sort by fewest active deliveries first, then oldest availability update /
    # earliest registration (so riders who have been idle/online longest get
    # the next order -- "first-in" fairness).
    candidates.sort(key=lambda r: (count_map.get(r.id, 0),
                                   r.availability_updated_at or r.date_joined))
    return candidates[0]


def pending_pool_for_rider(user):
    """SEARCHING orders a rider may see, ordered so that orders auto-assigned to
    THIS rider come first, then unassigned pool orders, then orders other riders
    are deciding on."""
    return (DeliveryRequest.objects
            .filter(status=DeliveryRequest.RequestStatus.SEARCHING)
            .filter(Q(assigned_to=user) | Q(assigned_to__isnull=True))
            .annotate(
                pool_rank=Case(
                    When(assigned_to=user, then=Value(0)),
                    When(assigned_to__isnull=True, then=Value(1)),
                    default=Value(2),
                    output_field=IntegerField(),
                )
            )
            .order_by('pool_rank', '-requested_at'))


def assign_next_searching_order(rider):
    """Auto-assign the oldest waiting (unassigned) SEARCHING order to a rider the
    moment they come online, so a queued order never idles waiting for a manual
    pick. Atomic (row-locked) so two riders going online at the exact same time
    can never both grab the same order.

    Returns the assigned DeliveryRequest, or None if nothing to hand out.
    """
    from django.db import transaction

    if rider.role not in ('RIDER', 'DELIVERY'):
        return None
    if not getattr(rider, 'is_available', False) or rider.account_status != 'active':
        return None

    active_count = DeliveryRequest.objects.filter(
        rider=rider, status=DeliveryRequest.RequestStatus.ACCEPTED
    ).count()
    if active_count >= 3:
        return None

    with transaction.atomic():
        candidate = (DeliveryRequest.objects
                     .select_for_update(skip_locked=True)
                     .filter(status=DeliveryRequest.RequestStatus.SEARCHING,
                             assigned_to__isnull=True)
                     .order_by('requested_at')
                     .first())
        if candidate is None:
            return None
        candidate.assigned_to = rider
        candidate.assigned_at = timezone.now()
        candidate.save(update_fields=['assigned_to', 'assigned_at'])
        return candidate


def rotate_to_next_rider(delivery, exclude_id=None):
    """Re-assign an unaccepted delivery to the next available rider in the
    round-robin. Returns True if reassigned to someone, False if none left."""
    from .models import DeliveryRequest

    if delivery.status != DeliveryRequest.RequestStatus.SEARCHING:
        return False

    next_rider = pick_next_available_rider(exclude_id=exclude_id)
    if next_rider is None:
        delivery.assigned_to = None
        delivery.assigned_at = None
        delivery.save(update_fields=['assigned_to', 'assigned_at'])
        return False

    delivery.assigned_to = next_rider
    delivery.assigned_at = timezone.now()
    delivery.save(update_fields=['assigned_to', 'assigned_at'])
    return True


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
