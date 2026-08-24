from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.http import JsonResponse
import json
from accounts.decorators import role_required
from .models import DeliveryRequest, DeliveryMessage

@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def delivery_dashboard(request):
    pending_deliveries = DeliveryRequest.objects.filter(status=DeliveryRequest.RequestStatus.SEARCHING).order_by('-requested_at')
    my_deliveries = DeliveryRequest.objects.filter(rider=request.user).exclude(status=DeliveryRequest.RequestStatus.REJECTED).order_by('-requested_at')
    
    # Calculate earnings (₱30 per completed delivery)
    completed_count = DeliveryRequest.objects.filter(rider=request.user, status=DeliveryRequest.RequestStatus.DELIVERED).count()
    total_earnings = completed_count * 30.00
    
    context = {
        'pending_deliveries': pending_deliveries,
        'my_deliveries': my_deliveries,
        'completed_count': completed_count,
        'total_earnings': total_earnings,
    }
    return render(request, 'delivery_dashboard.html', context)

@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN'])
def accept_delivery(request, delivery_id):
    delivery = get_object_or_404(DeliveryRequest, id=delivery_id)
    if delivery.status == DeliveryRequest.RequestStatus.SEARCHING:
        delivery.status = DeliveryRequest.RequestStatus.ACCEPTED
        delivery.rider = request.user
        delivery.accepted_at = timezone.now()
        delivery.save()

        order = delivery.order
        order.status = 'pending'
        order.save()

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

    return redirect('deliveries:dashboard')

@role_required(allowed_roles=['RIDER', 'DELIVERY', 'STAFF', 'ADMIN', 'FACULTY'])
def get_delivery_messages(request, delivery_id):
    delivery = get_object_or_404(DeliveryRequest, id=delivery_id)
    messages = delivery.messages.all().order_by('timestamp')
    msg_list = [{
        'sender': m.sender.username,
        'is_me': m.sender == request.user,
        'message': m.message,
        'time': m.timestamp.strftime('%H:%M')
    } for m in messages]
    return JsonResponse({'success': True, 'messages': msg_list})

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
                    message=text
                )
                return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False}, status=400)
