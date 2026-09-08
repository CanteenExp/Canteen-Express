from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, StreamingHttpResponse
import json
import time
from datetime import timedelta
from accounts.decorators import role_required
from .models import DeliveryRequest, DeliveryMessage, RiderLocationPoint
from .utils import haversine_km, distance_from_points, compute_speed_kmh, compute_bearing, is_within_campus

# How long a delivery waits as a proposal with NO online rider before timing out.
UNASSIGNED_TIMEOUT_MINUTES = 5


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def delivery_dashboard(request, token=None):
    import uuid
    from django.urls import reverse
    session_token = request.session.get('rider_secure_token')
    if not session_token:
        session_token = uuid.uuid4().hex[:12]
        request.session['rider_secure_token'] = session_token

    if not token or token != session_token:
        query_string = request.META.get('QUERY_STRING', '')
        redirect_url = reverse('deliveries:dashboard_hashed', kwargs={'token': session_token})
        if query_string:
            redirect_url += f'?{query_string}'
        return redirect(redirect_url)
    expire_stale_requests()

    # Incoming pool: every SEARCHING proposal in the shared pool. Nothing is
    # pre-assigned -- whichever online rider accepts first claims the order.
    from .utils import pending_pool_for_rider
    pending_deliveries = pending_pool_for_rider(request.user)

    my_deliveries = DeliveryRequest.objects.filter(
        rider=request.user
    ).exclude(status=DeliveryRequest.RequestStatus.REJECTED).order_by('-requested_at')

    # Split the rider's work into clearly separate groups: orders the rider is
    # CURRENTLY delivering (accepted, in transit) vs. ones already DELIVERED so
    # the dashboard never mixes "being delivered" with "already delivered".
    in_transit_deliveries = DeliveryRequest.objects.filter(
        rider=request.user, status=DeliveryRequest.RequestStatus.ACCEPTED
    ).order_by('-requested_at')

    completed_deliveries = DeliveryRequest.objects.filter(
        rider=request.user, status=DeliveryRequest.RequestStatus.DELIVERED
    ).order_by('-delivered_at')[:15]

    completed_count = DeliveryRequest.objects.filter(
        rider=request.user, status=DeliveryRequest.RequestStatus.DELIVERED
    ).count()
    completed_qs = DeliveryRequest.objects.filter(
        rider=request.user, status=DeliveryRequest.RequestStatus.DELIVERED
    )
    total_earnings = sum(float(d.order.delivery_fee) for d in completed_qs)
    active_deliveries_count = DeliveryRequest.objects.filter(
        rider=request.user, status=DeliveryRequest.RequestStatus.ACCEPTED
    ).count()

    context = {
        'pending_deliveries': pending_deliveries,
        'my_deliveries': my_deliveries,
        'in_transit_deliveries': in_transit_deliveries,
        'completed_deliveries': completed_deliveries,
        'completed_count': completed_count,
        'total_earnings': total_earnings,
        'active_deliveries_count': active_deliveries_count,
        'is_available': getattr(request.user, 'is_available', True),
        'reachable_loc_count': pending_deliveries.count(),
    }
    return render(request, 'delivery_dashboard.html', context)


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def pending_cards(request):
    """HTML fragment of the incoming-pool grid used by the rider dashboard so a
    brand-new faculty order can be re-rendered instantly (no page reload) via SSE.
    """
    expire_stale_requests()
    from .utils import pending_pool_for_rider
    pending_deliveries = pending_pool_for_rider(request.user)
    active_deliveries_count = DeliveryRequest.objects.filter(
        rider=request.user, status=DeliveryRequest.RequestStatus.ACCEPTED
    ).count()
    return render(request, 'partials/pending_delivery_cards.html', {
        'pending_deliveries': pending_deliveries,
        'active_deliveries_count': active_deliveries_count,
    })


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def delivery_history(request):
    history = DeliveryRequest.objects.filter(
        rider=request.user
    ).order_by('-requested_at')

    completed_count = history.filter(
        status=DeliveryRequest.RequestStatus.DELIVERED
    ).count()
    total_earnings = sum(
        float(d.order.delivery_fee)
        for d in history.filter(status=DeliveryRequest.RequestStatus.DELIVERED)
    )

    context = {
        'history': history,
        'completed_count': completed_count,
        'total_earnings': total_earnings,
    }
    return render(request, 'delivery_history.html', context)


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def toggle_availability(request):
    user = request.user
    was_available = getattr(user, 'is_available', True)
    user.is_available = not was_available
    user.availability_updated_at = timezone.now()
    user.save(update_fields=['is_available', 'availability_updated_at'])

    # Coming online only makes the rider part of the pool -- proposals (the
    # shared SEARCHING queue) are never handed to a specific rider in advance.
    # The sweep still runs so any ready delivery that timed out revives for
    # everyone to see.
    if user.is_available and not was_available:
        expire_stale_requests()

    return JsonResponse({
        'success': True,
        'is_available': user.is_available,
        'assigned_order': None,
    })


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def accept_delivery(request, delivery_id):
    from django.db import transaction

    # Offline riders are not allowed to accept new requests.
    if not getattr(request.user, 'is_available', True):
        messages.error(request, 'Go online to receive and accept new requests.')
        return redirect('deliveries:dashboard')

    # Atomic compare-and-set: lock the delivery row so two riders can never both
    # accept the same request (prevents the accept/double-assignment race).
    with transaction.atomic():
        delivery = DeliveryRequest.objects.select_for_update().get(id=delivery_id)

        active_count = DeliveryRequest.objects.filter(
            rider=request.user, status=DeliveryRequest.RequestStatus.ACCEPTED
        ).count()
        if active_count >= 3:
            messages.error(request, 'Max 3 active deliveries reached. Complete one first.')
            return redirect('deliveries:dashboard')

        if delivery.status == DeliveryRequest.RequestStatus.SEARCHING:
            delivery.status = DeliveryRequest.RequestStatus.ACCEPTED
            delivery.rider = request.user
            delivery.assigned_to = None
            delivery.accepted_at = timezone.now()
            delivery.save()

            order = delivery.order
            if order.status != 'ready':
                order.status = 'pending'
                order.save()
            messages.success(request, f'Delivery {delivery.order.order_number} accepted!')

    return redirect('deliveries:dashboard')


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def reject_delivery(request, delivery_id):
    from django.db import transaction

    # Under the proposal-only model nothing is pre-assigned; rejecting just
    # drops any stale "offered" rider so the order stays visible to everyone
    # in the shared pool. Staff can always dismiss a proposal.
    with transaction.atomic():
        delivery = DeliveryRequest.objects.select_for_update().get(id=delivery_id)
        if delivery.status == DeliveryRequest.RequestStatus.SEARCHING:
            delivery.assigned_to = None
            delivery.assigned_at = None
            delivery.save(update_fields=['assigned_to', 'assigned_at'])

    return redirect('deliveries:dashboard')


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def complete_delivery(request, delivery_id):
    delivery = get_object_or_404(DeliveryRequest, id=delivery_id, rider=request.user)
    if delivery.status == DeliveryRequest.RequestStatus.ACCEPTED:
        delivery.status = DeliveryRequest.RequestStatus.DELIVERED
        delivery.delivered_at = timezone.now()
        delivery.save()

        order = delivery.order
        order.status = 'completed'
        order.save()
        earned = float(order.delivery_fee)
        messages.success(request, f'Delivery {delivery.order.order_number} completed! +₱{earned:.0f} earned.')

    return redirect('deliveries:dashboard')


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def cancel_delivery(request, delivery_id):
    from django.db import transaction

    # Releasing an accepted delivery returns it to the shared pool as a fresh
    # proposal for every online rider (no pre-assignment to a specific rider).
    with transaction.atomic():
        delivery = DeliveryRequest.objects.select_for_update().get(id=delivery_id, rider=request.user)
        if delivery.status == DeliveryRequest.RequestStatus.ACCEPTED:
            delivery.status = DeliveryRequest.RequestStatus.SEARCHING
            delivery.rider = None
            delivery.assigned_to = None
            delivery.assigned_at = None
            delivery.accepted_at = None
            delivery.save()

            order = delivery.order
            if order.status != 'ready':
                order.status = 'pending'
                order.save()

    return redirect('deliveries:dashboard')


def expire_stale_requests():
    """Keep the search phase honest under a PROPOSE-ONLY model.

    A SEARCHING delivery is a *proposal* displayed to every online rider; it is
    never assigned to a specific rider until one taps Accept. So:

    0) REVIVE: a delivery whose food is READY but that timed out while no rider
       was online comes back to life the moment any rider shows up -- ready
       meals never stay stranded. The fresh clock gives it a full search window.
    1) PROPOSE-ONLY: sweep away any legacy pre-assigned offer on a SEARCHING
       order so nothing reads as "assigned" before it is actually accepted.
    2) PRUNE: only a true orphan (a proposal nobody could accept because NO rider
       is online for a long while) is dropped to TIMEOUT. While riders are
       online the proposal simply stays -- whoever accepts first wins.
    """
    now = timezone.now()

    # 0) REVIVE ready deliveries that timed out while no rider was around.
    DeliveryRequest.objects.filter(
        status=DeliveryRequest.RequestStatus.TIMEOUT,
        order__status__in=['ready', 'preparing'],
    ).update(
        status=DeliveryRequest.RequestStatus.SEARCHING,
        requested_at=now,
        assigned_to=None,
        assigned_at=None,
    )

    # 1) Proposal-only: no pre-assigned rider until one accepts.
    DeliveryRequest.objects.filter(
        status=DeliveryRequest.RequestStatus.SEARCHING,
        assigned_to__isnull=False,
    ).update(assigned_to=None, assigned_at=None)

    # 2) True orphans only: no rider online at all for a while.
    from django.contrib.auth import get_user_model
    from accounts.models import CustomUser
    User = get_user_model()
    any_online = User.objects.filter(
        role__in=['RIDER', 'DELIVERY'],
        is_available=True,
        account_status='active',
        availability_updated_at__gte=now - CustomUser.RIDER_ONLINE_TIMEOUT,
    ).exists()
    if not any_online:
        orphan_cutoff = now - timedelta(minutes=UNASSIGNED_TIMEOUT_MINUTES)
        DeliveryRequest.objects.filter(
            status=DeliveryRequest.RequestStatus.SEARCHING,
            assigned_to__isnull=True,
            requested_at__lte=orphan_cutoff,
        ).update(status=DeliveryRequest.RequestStatus.TIMEOUT)


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN', 'FACULTY'])
def get_delivery_messages(request, delivery_id):
    delivery = get_object_or_404(DeliveryRequest, id=delivery_id)
    user = request.user
    is_rider = delivery.rider == user
    is_customer = delivery.order.customer == user
    is_privileged = user.role in ('STAFF', 'ADMIN')
    if not (is_rider or is_customer or is_privileged):
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
    messages_qs = delivery.messages.all().order_by('timestamp')
    # Mark incoming messages as read now that the user has the chat open
    unread_ids = delivery.messages.filter(is_read=False).exclude(sender=request.user).count()
    delivery.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    msg_list = [{
        'id': m.id,
        'sender': m.sender.username,
        'sender_role': m.sender.role,
        'is_me': m.sender == request.user,
        'message': m.message,
        'time': m.timestamp.strftime('%H:%M'),
    } for m in messages_qs]
    return JsonResponse({'success': True, 'messages': msg_list, 'unread_count': unread_ids})


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN', 'FACULTY'])
def send_delivery_message(request, delivery_id):
    if request.method == 'POST':
        try:
            delivery = get_object_or_404(DeliveryRequest, id=delivery_id)
            user = request.user
            is_rider = delivery.rider == user
            is_customer = delivery.order.customer == user
            is_privileged = user.role in ('STAFF', 'ADMIN')
            if not (is_rider or is_customer or is_privileged):
                return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
            data = json.loads(request.body)
            text = data.get('message', '').strip()
            if text:
                DeliveryMessage.objects.create(
                    delivery=delivery,
                    sender=request.user,
                    message=text,
                )
                return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False}, status=400)


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def pool_status(request):
    """Lightweight status used by the dashboard to live-refresh the incoming pool."""
    expire_stale_requests()
    # Incoming pool: every SEARCHING order, visible to all online riders.
    from .utils import pending_pool_for_rider
    pending_ids = list(pending_pool_for_rider(request.user).values_list('id', flat=True))

    active_ids = list(DeliveryRequest.objects.filter(
        rider=request.user, status=DeliveryRequest.RequestStatus.ACCEPTED
    ).values_list('id', flat=True))

    # Unread chat counts across the rider's accepted deliveries
    unread = {}
    for d in DeliveryRequest.objects.filter(rider=request.user).exclude(
        status=DeliveryRequest.RequestStatus.REJECTED):
        count = d.messages.filter(is_read=False).exclude(sender=request.user).count()
        if count:
            unread[d.id] = count

    return JsonResponse({
        'success': True,
        'pending_ids': pending_ids,
        'pending_count': len(pending_ids),
        'active_ids': active_ids,
        'active_count': len(active_ids),
        'unread': unread,
        'total_unread': sum(unread.values()),
    })


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def get_order_detail(request, delivery_id):
    """Detailed order info (with per-item prices) for the rider's detail modal."""
    delivery = get_object_or_404(DeliveryRequest, id=delivery_id)
    order = delivery.order
    items = [{
        'name': it.item_name,
        'qty': it.quantity,
        'price': float(it.price),
        'total': float(it.total_price),
    } for it in order.items.all()]

    customer = order.customer
    customer_name = None
    customer_phone = None
    if customer:
        customer_name = customer.get_full_name() or customer.username
        customer_phone = customer.phone or None

    return JsonResponse({
        'success': True,
        'order_number': order.order_number,
        'status': order.get_status_display(),
        'created_at': order.created_at.strftime('%b %d, %Y %I:%M %p'),
        'items': items,
        'subtotal': float(order.total_amount),
        'delivery_fee': float(order.delivery_fee),
        'total_payment': float(order.total_payment),
        'delivery_location': delivery.delivery_location,
        'customer_name': customer_name,
        'customer_phone': customer_phone,
    })


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def update_location(request, delivery_id):
    """Rider pushes their live GPS position for a delivery."""
    if request.method == 'POST':
        try:
            delivery = get_object_or_404(
                DeliveryRequest, id=delivery_id, rider=request.user)
            if delivery.status not in (
                DeliveryRequest.RequestStatus.ACCEPTED,
                DeliveryRequest.RequestStatus.DELIVERED,
            ):
                return JsonResponse({'success': False, 'message': 'Delivery not active'}, status=400)
            data = json.loads(request.body)
            lat = data.get('lat')
            lng = data.get('lng')
            if lat is None or lng is None:
                return JsonResponse({'success': False, 'message': 'Missing coordinates'}, status=400)
            lat = float(lat)
            lng = float(lng)

            # Campus-only scope: reject location pushes outside the campus geofence
            if not is_within_campus(lat, lng):
                return JsonResponse({
                    'success': False,
                    'message': 'Location is outside the campus delivery zone'
                }, status=422)

            # Compute live speed from the previous known position
            now = timezone.now()
            prev = delivery.location_points.order_by('-timestamp').first()
            speed = 0.0
            if prev is not None and prev.lat is not None and prev.lng is not None:
                speed = compute_speed_kmh(
                    prev.lat, prev.lng, prev.timestamp, lat, lng, now)

            RiderLocationPoint.objects.create(
                delivery=delivery,
                rider=request.user,
                lat=lat,
                lng=lng,
                speed_kmh=speed,
            )
            delivery.rider_lat = lat
            delivery.rider_lng = lng
            delivery.location_updated_at = now
            delivery.save(update_fields=['rider_lat', 'rider_lng', 'location_updated_at'])
            return JsonResponse({'success': True, 'speed_kmh': round(speed, 1)})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False}, status=400)


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN', 'FACULTY'])
def get_tracking(request, delivery_id):
    """Return the rider's latest position plus speed/distance/ETA for live tracking."""
    delivery = get_object_or_404(DeliveryRequest, id=delivery_id)

    points = list(delivery.location_points.all())
    total_distance_km = distance_from_points([(p.lat, p.lng) for p in points])

    latest_speed = points[-1].speed_kmh if points else 0.0

    # Heading (direction of travel) from the last two location points
    heading = None
    if len(points) >= 2:
        heading = compute_bearing(points[-2].lat, points[-2].lng, points[-1].lat, points[-1].lng)

    remaining_km = None
    eta_minutes = None
    if delivery.dest_lat is not None and delivery.rider_lat is not None:
        remaining_km = haversine_km(
            delivery.rider_lat, delivery.rider_lng, delivery.dest_lat, delivery.dest_lng)
        if latest_speed > 0.5 and delivery.status != DeliveryRequest.RequestStatus.DELIVERED:
            eta_minutes = (remaining_km / latest_speed) * 60.0
        else:
            eta_minutes = None

    return JsonResponse({
        'success': True,
        'status': delivery.status,
        'lat': delivery.rider_lat,
        'lng': delivery.rider_lng,
        'dest_lat': delivery.dest_lat,
        'dest_lng': delivery.dest_lng,
        'speed_kmh': round(latest_speed, 1),
        'heading': round(heading, 1) if heading is not None else None,
        'total_distance_km': round(total_distance_km, 2),
        'remaining_km': round(remaining_km, 2) if remaining_km is not None else None,
        'eta_minutes': round(eta_minutes) if eta_minutes is not None else None,
        'updated_at': delivery.location_updated_at.strftime('%I:%M %p') if delivery.location_updated_at else None,
        'order_number': delivery.order.order_number,
        'delivery_location': delivery.delivery_location,
    })


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN', 'FACULTY'])
def track_order(request, delivery_id):
    """Customer-facing live tracking page (Leaflet map)."""
    delivery = get_object_or_404(DeliveryRequest, id=delivery_id)
    order = delivery.order
    is_customer = (
        request.user.is_authenticated and order.customer is not None
        and order.customer == request.user
    ) or request.user.role in ['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'] or request.user.is_superuser
    if not is_customer and not (request.user.is_authenticated and request.user.role == 'FACULTY'):
        messages.error(request, "Access denied.")
        return redirect('accounts:landing')

    context = {
        'delivery': delivery,
        'order': order,
        'order_number': order.order_number,
        'delivery_location': delivery.delivery_location,
        'status': delivery.status,
        'rider_name': delivery.rider.get_full_name() or delivery.rider.username if delivery.rider else None,
    }
    return render(request, 'delivery_tracking.html', context)


@role_required(allowed_roles=['STUDENT', 'FACULTY'])
def faculty_delivery_status(request):
    """Polling endpoint for the faculty/student dashboard to live-sync delivery statuses."""
    from .utils import serialize_delivery
    if request.user.is_authenticated:
        deliveries = DeliveryRequest.objects.filter(
            order__customer=request.user).order_by('-requested_at')[:5]
    else:
        deliveries = []
    data = [serialize_delivery(d) for d in deliveries]
    return JsonResponse({'success': True, 'deliveries': data})


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def rider_earnings_summary(request):
    """Real-time earnings summary for the rider dashboard (polled by JS)."""
    completed_qs = DeliveryRequest.objects.filter(
        rider=request.user, status=DeliveryRequest.RequestStatus.DELIVERED
    )
    total_earnings = sum(
        float(d.order.delivery_fee) for d in completed_qs)
    return JsonResponse({
        'success': True,
        'total_earnings': total_earnings,
        'completed_count': completed_qs.count(),
    })


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def rider_live_stream(request):
    """
    Unified real-time Server-Sent Events (SSE) stream for the rider dashboard.

    Replaces the fragmented set of HTTP polls (pool status @7s, earnings @4s,
    chat @2s) with a single stream that pushes the instant anything changes:
      - incoming delivery pool (new request, expiry)
      - active orders + their current status
      - unread chat counts and a flag when a new chat arrives
      - current delivery earnings (based on delivered orders, per full ₱300)
    """
    import hashlib
    from .utils import serialize_delivery

    def event_stream():
        last_hash = None
        last_chat_hash = None
        last_expire = 0.0
        last_heartbeat = 0.0
        # Proposal-only pool: nothing is pre-assigned to this rider. The stream
        # just reports the shared SEARCHING queue; accepting happens in
        # accept_delivery, not automatically.
        while True:
            try:
                # Throttle the assignment/expiry writes (they only matter on a
                # short cadence) so the real-time read loop stays light on the DB.
                now = time.time()
                if now - last_expire >= 10:
                    expire_stale_requests()
                    last_expire = now

                # Presence heartbeat: while this SSE stream is alive the rider is
                # genuinely "online". A fresh timestamp keeps is_really_online True
                # on staff dashboards; when the connection drops, no more
                # heartbeats arrive and the rider drops back to Offline within
                # RIDER_ONLINE_TIMEOUT.
                if now - last_heartbeat >= 30:
                    last_heartbeat = now
                    from django.contrib.auth import get_user_model
                    get_user_model().objects.filter(
                        pk=request.user.pk, is_available=True
                    ).update(availability_updated_at=timezone.now())

                pending_ids = list(pending_pool_for_rider(request.user).values_list('id', flat=True))

                my_deliveries = DeliveryRequest.objects.filter(
                    rider=request.user).exclude(
                        status=DeliveryRequest.RequestStatus.REJECTED)
                active = [serialize_delivery(d) for d in my_deliveries.filter(
                    status=DeliveryRequest.RequestStatus.ACCEPTED)]

                completed_qs = my_deliveries.filter(
                    status=DeliveryRequest.RequestStatus.DELIVERED)
                total_earnings = sum(
                    float(d.order.delivery_fee) for d in completed_qs)

                unread = {}
                total_unread = 0
                chat_digest = None
                for d in my_deliveries:
                    last = d.messages.order_by('-timestamp').first()
                    if last is not None:
                        current = f"{d.id}:{last.id}:{last.timestamp.timestamp()}"
                        chat_digest = (chat_digest + '|' + current) if chat_digest else current
                    count = last__count_for(d, request.user)
                    if count:
                        unread[d.id] = count
                        total_unread += count

                payload = {
                    'success': True,
                    'pending_ids': pending_ids,
                    'pending_count': len(pending_ids),
                    'active': active,
                    'active_count': len(active),
                    'unread': unread,
                    'total_unread': total_unread,
                    'total_earnings': round(total_earnings, 2),
                    'completed_count': completed_qs.count(),
                    'chat_updated': False,
                }
                if chat_digest is not None and chat_digest != last_chat_hash:
                    last_chat_hash = chat_digest
                    payload['chat_updated'] = True

                body = json.dumps(payload)
                digest = hashlib.md5(body.encode('utf-8')).hexdigest()
                if digest != last_hash:
                    last_hash = digest
                    yield f"data: {body}\n\n"
            except Exception:
                pass
            yield ": ping\n\n"
            time.sleep(1.5)

    return StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )


def last__count_for(d, user):
    """Return the number of unread messages sent by the other party."""
    return d.messages.filter(is_read=False).exclude(sender=user).count()


@role_required(allowed_roles=['STUDENT', 'FACULTY'])
def faculty_delivery_stream(request):
    """
    Real-time Server-Sent Events (SSE) stream for the faculty/student dashboard.

    Pushes a single unified payload the moment anything changes:
      - order status (e.g. rider marks DELIVERED -> faculty can reorder)
      - the rider's live GPS position (so tracking is real-time)
    Includes lightweight chat metadata so the client only refetches messages when
    there is something new, instead of polling every 1-2 seconds.
    """
    import hashlib
    from .utils import serialize_delivery

    def event_stream():
        last_hash = None
        last_chat_hash = None
        while True:
            try:
                deliveries = DeliveryRequest.objects.filter(
                    order__customer=request.user).order_by('-requested_at')[:5]
                data = [serialize_delivery(d) for d in deliveries]

                payload = {
                    'success': True,
                    'deliveries': data,
                    'chat_updated': False,
                }
                # Detect new/updated chat messages for any of the user's deliveries
                # so the client can fetch messages instantly (real-time chat) without
                # a busy 2-second poll.
                chat_digest = None
                chat_deliveries = DeliveryRequest.objects.filter(
                    order__customer=request.user).exclude(
                        status=DeliveryRequest.RequestStatus.SEARCHING)
                for d in chat_deliveries:
                    last = d.messages.order_by('-timestamp').first()
                    if last is not None:
                        current = f"{d.id}:{last.id}:{last.timestamp.timestamp()}"
                        chat_digest = (chat_digest + '|' + current) if chat_digest else current
                if chat_digest is not None and chat_digest != last_chat_hash:
                    last_chat_hash = chat_digest
                    payload['chat_updated'] = True

                body = json.dumps(payload)
                digest = hashlib.md5(body.encode('utf-8')).hexdigest()
                if digest != last_hash:
                    last_hash = digest
                    yield f"data: {body}\n\n"
            except Exception:
                # Keep the stream alive; the client will re-open on failure.
                pass
            # Heartbeat to keep the connection open and detect drops fast.
            yield ": ping\n\n"
            time.sleep(1.5)

    return StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def staff_dispatch_stream(request):
    """
    Real-time Server-Sent Events (SSE) stream for the staff dashboard's
    "Live Delivery Dispatches" table.

    Emits a lightweight digest of all delivery requests (id/status/order number/
    location/rider) so the table can refresh in place the moment a request is
    created, accepted, or delivered -- no page reload, no blind 5s polling.
    """
    import hashlib
    from django.contrib.auth import get_user_model
    User = get_user_model()

    def dispatch_map(d):
        # A rider is 'offered' an order (assigned_to) before they accept it
        # (rider). Show whichever applies so the dispatch table never reads
        # "Unassigned" while an online rider already has the offer.
        rider = d.rider or d.assigned_to
        return {
            'id': d.id,
            'order_number': d.order.order_number if d.order else '—',
            'location': d.delivery_location,
            'rider': rider.get_full_name() if (rider and rider.get_full_name()) else (rider.username if rider else 'Unassigned'),
            'status': d.status,
        }

    def event_stream():
        last_hash = None
        while True:
            try:
                requests = DeliveryRequest.objects.all().order_by('-requested_at')[:20]
                # Live rider availability so the staff portal always shows the
                # true "online = ready for assignment" status, not the account
                # status.
                riders = User.objects.filter(role__in=['RIDER', 'DELIVERY'])
                payload = {
                    'success': True,
                    'dispatches': [dispatch_map(d) for d in requests],
                    'riders': [{
                        'id': r.id,
                        'username': r.username,
                        'name': r.get_full_name() or r.username,
                        'is_available': r.is_available,
                        'online': r.is_really_online,
                        'is_active': r.is_active,
                        'account_status': r.account_status,
                    } for r in riders],
                }
                body = json.dumps(payload)
                digest = hashlib.md5(body.encode('utf-8')).hexdigest()
                if digest != last_hash:
                    last_hash = digest
                    yield f"data: {body}\n\n"
            except Exception:
                pass
            yield ": ping\n\n"
            time.sleep(2)

    return StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )
