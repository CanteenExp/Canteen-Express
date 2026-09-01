from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
import json
from datetime import timedelta
from accounts.decorators import role_required
from .models import DeliveryRequest, DeliveryMessage, RiderLocationPoint
from .utils import haversine_km, distance_from_points, compute_speed_kmh, compute_bearing, is_within_campus

REQUEST_TIMEOUT_MINUTES = 5


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def delivery_dashboard(request):
    expire_stale_requests()

    pending_deliveries = DeliveryRequest.objects.filter(
        status=DeliveryRequest.RequestStatus.SEARCHING
    ).order_by('-requested_at')

    my_deliveries = DeliveryRequest.objects.filter(
        rider=request.user
    ).exclude(status=DeliveryRequest.RequestStatus.REJECTED).order_by('-requested_at')

    completed_count = DeliveryRequest.objects.filter(
        rider=request.user, status=DeliveryRequest.RequestStatus.DELIVERED
    ).count()
    total_earnings = completed_count * 30.00
    active_deliveries_count = DeliveryRequest.objects.filter(
        rider=request.user, status=DeliveryRequest.RequestStatus.ACCEPTED
    ).count()

    context = {
        'pending_deliveries': pending_deliveries,
        'my_deliveries': my_deliveries,
        'completed_count': completed_count,
        'total_earnings': total_earnings,
        'active_deliveries_count': active_deliveries_count,
        'is_available': getattr(request.user, 'is_available', True),
        'reachable_loc_count': pending_deliveries.count(),
    }
    return render(request, 'delivery_dashboard.html', context)


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def delivery_history(request):
    history = DeliveryRequest.objects.filter(
        rider=request.user
    ).order_by('-requested_at')

    completed_count = history.filter(
        status=DeliveryRequest.RequestStatus.DELIVERED
    ).count()
    total_earnings = completed_count * 30.00

    context = {
        'history': history,
        'completed_count': completed_count,
        'total_earnings': total_earnings,
    }
    return render(request, 'delivery_history.html', context)


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def toggle_availability(request):
    user = request.user
    user.is_available = not getattr(user, 'is_available', True)
    user.availability_updated_at = timezone.now()
    user.save(update_fields=['is_available', 'availability_updated_at'])
    return JsonResponse({'success': True, 'is_available': user.is_available})


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def accept_delivery(request, delivery_id):
    delivery = get_object_or_404(DeliveryRequest, id=delivery_id)
    active_count = DeliveryRequest.objects.filter(
        rider=request.user, status=DeliveryRequest.RequestStatus.ACCEPTED
    ).count()
    if active_count >= 3:
        messages.error(request, 'Max 3 active deliveries reached. Complete one first.')
        return redirect('deliveries:dashboard')

    if delivery.status == DeliveryRequest.RequestStatus.SEARCHING:
        delivery.status = DeliveryRequest.RequestStatus.ACCEPTED
        delivery.rider = request.user
        delivery.accepted_at = timezone.now()
        delivery.save()

        order = delivery.order
        order.status = 'pending'
        order.save()
        messages.success(request, f'Delivery {delivery.order.order_number} accepted!')

    return redirect('deliveries:dashboard')


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def reject_delivery(request, delivery_id):
    delivery = get_object_or_404(DeliveryRequest, id=delivery_id)
    if delivery.status == DeliveryRequest.RequestStatus.SEARCHING:
        delivery.status = DeliveryRequest.RequestStatus.REJECTED
        delivery.save()
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
        messages.success(request, f'Delivery {delivery.order.order_number} completed! +₱30 earned.')

    return redirect('deliveries:dashboard')


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def cancel_delivery(request, delivery_id):
    delivery = get_object_or_404(DeliveryRequest, id=delivery_id, rider=request.user)
    if delivery.status == DeliveryRequest.RequestStatus.ACCEPTED:
        delivery.status = DeliveryRequest.RequestStatus.REJECTED
        delivery.rider = None
        delivery.accepted_at = None
        delivery.save()

        order = delivery.order
        order.status = 'pending'
        order.save()
    return redirect('deliveries:dashboard')


def expire_stale_requests():
    cutoff = timezone.now() - timedelta(minutes=REQUEST_TIMEOUT_MINUTES)
    expired = DeliveryRequest.objects.filter(
        status=DeliveryRequest.RequestStatus.SEARCHING,
        requested_at__lte=cutoff,
    )
    for d in expired:
        d.status = DeliveryRequest.RequestStatus.TIMEOUT
    expired.update(status=DeliveryRequest.RequestStatus.TIMEOUT)


@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN', 'FACULTY'])
def get_delivery_messages(request, delivery_id):
    delivery = get_object_or_404(DeliveryRequest, id=delivery_id)
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
    pending_ids = list(DeliveryRequest.objects.filter(
        status=DeliveryRequest.RequestStatus.SEARCHING
    ).values_list('id', flat=True))

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
