import json
import random
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from canteen_menu.models import MenuItem
from .models import Order, OrderItem


# Helper function to format active DB menu items for Kiosk JSON (with in-memory caching for lightning fast performance)
def _get_formatted_menu():
    cache_key = 'formatted_menu_active_kiosk'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    db_items = MenuItem.objects.filter(is_available=True).order_by('-id')
    formatted_menu = []
    for item in db_items:
        img_url = ''
        if hasattr(item, 'get_image_src'):
            attr = getattr(item, 'get_image_src')
            img_url = attr() if callable(attr) else attr
        elif hasattr(item, 'image') and item.image:
            try:
                img_url = item.image.url
            except ValueError:
                img_url = ''

        category_str = 'General'
        if hasattr(item, 'category') and item.category:
            category_str = item.category.name if hasattr(item.category, 'name') else str(item.category)

        formatted_menu.append({
            'id': item.id,
            'name': item.name,
            'category': category_str,
            'price': float(item.price) if item.price else 0.0,
            'desc': getattr(item, 'description', '') or getattr(item, 'desc', '') or '',
            'badge': getattr(item, 'badge', '') or '',
            'isSiomai': getattr(item, 'is_siomai', False) or getattr(item, 'isSiomai', False),
            'img': img_url
        })
    cache.set(cache_key, formatted_menu, 60)
    return formatted_menu


# 1. CUSTOMER SIDE - Landing Page
def kiosk_welcome(request):
    return render(request, 'customer_portal/kiosk_welcome.html')


# 2. CUSTOMER SIDE - Main Menu Page
def kiosk_menu(request):
    formatted_menu = _get_formatted_menu()
    context = {
        'menu_data_json': json.dumps(formatted_menu)
    }
    return render(request, 'customer_portal/kiosk_menu.html', context)


# 3. CUSTOMER SIDE - Live Sync API
def get_kiosk_menu_api(request):
    formatted_menu = _get_formatted_menu()
    return JsonResponse({'status': 'success', 'menu': formatted_menu})


# 4. CUSTOMER SIDE - Checkout Endpoint
@require_POST
def process_checkout(request):
    try:
        data = json.loads(request.body)
        cart_items = data.get('cart', [])
        is_delivery = data.get('is_delivery', False)
        delivery_location = data.get('delivery_location', 'Faculty Office Building')

        if not cart_items:
            return JsonResponse({'success': False, 'message': 'Cart is empty.'}, status=400)

        # Server-authoritative subtotal: recomputed from the cart payload so the
        # stored total, delivery fee, and final payment can never drift from each
        # other (a client-sent total_amount is ignored on purpose).
        try:
            subtotal = sum(
                round(float(item.get('price', 0)) * int(item.get('qty', 0)), 2)
                for item in cart_items
            )
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'message': 'Invalid cart item price or quantity.'}, status=400)

        # Campus-only scope: validate delivery destination BEFORE creating the order.
        # If the customer's location (GPS or building preset) falls outside the PSU
        # campus geofence, the whole order is rejected.
        if is_delivery:
            from deliveries.utils import is_within_campus, delivery_fee_for_order
            dest_lat = data.get('dest_lat')
            dest_lng = data.get('dest_lng')
            from django.conf import settings
            enforce_geofence = getattr(settings, 'ENFORCE_GEOFENCE', True)
            if enforce_geofence and not is_within_campus(dest_lat, dest_lng):
                return JsonResponse({
                    'success': False,
                    'message': 'Delivery is only available within the Palawan State University campus. Please make sure your location is inside the campus and try again.'
                }, status=422)

        points_redeemed = float(data.get('points_redeemed', 0) or 0)
        points_earned = round(subtotal * 0.1, 1)

        user = request.user if request.user.is_authenticated else None
        if user:
            if points_redeemed > 0:
                if float(getattr(user, 'loyalty_points', 0)) >= points_redeemed:
                    user.loyalty_points = float(user.loyalty_points) - points_redeemed
                else:
                    return JsonResponse({'success': False, 'message': 'Insufficient loyalty points.'}, status=400)
            user.loyalty_points = float(user.loyalty_points) + points_earned
            user.save()

        # Generate a unique order number that avoids colliding with existing
        # orders (the column is UNIQUE, and a 4-digit random can repeat ~1/9000).
        def _unique_order_number():
            while True:
                candidate = f"#CE-{random.randint(1000, 9999)}"
                if not Order.objects.filter(order_number=candidate).exists():
                    return candidate

        order_number = _unique_order_number()
        initial_status = 'pending' if is_delivery else 'unpaid'
        
        # Delivery fee = rider earning: ₱15 per ₱300 block of the order subtotal.
        # It is a separate line from the food total and belongs to the rider.
        from deliveries.utils import delivery_fee_for_order
        delivery_fee = delivery_fee_for_order(subtotal) if is_delivery else 0.0

        # Wrap the whole order pipeline in a transaction so a failure anywhere
        # rolls back everything: no orphaned Order without its DeliveryRequest
        # (which would be invisible to riders in the incoming pool).
        with transaction.atomic():
            order = Order.objects.create(
                order_number=order_number,
                total_amount=subtotal,
                delivery_fee=delivery_fee,
                status=initial_status,
                customer=request.user if request.user.is_authenticated else None
            )

            from queuing.models import DigitalQueueSlip
            try:
                DigitalQueueSlip.objects.get_or_create(
                    order=order,
                    defaults={'queue_number': order_number}
                )
            except Exception:
                pass

            for item in cart_items:
                qty = int(item.get('qty', 1))
                item_name = item.get('name', '')
                item_id = item.get('id')

                OrderItem.objects.create(
                    order=order,
                    item_name=item_name,
                    price=item.get('price', 0),
                    quantity=qty
                )

                menu_item = None
                if item_id:
                    menu_item = MenuItem.objects.filter(id=item_id).first()
                if not menu_item and item_name:
                    menu_item = MenuItem.objects.filter(name__iexact=item_name).first()

                if menu_item:
                    if hasattr(menu_item, 'stock') and menu_item.stock is not None:
                        if menu_item.stock >= qty:
                            menu_item.stock -= qty
                        else:
                            menu_item.stock = 0
                        if menu_item.stock <= 0:
                            menu_item.is_available = False
                        menu_item.save()

            if is_delivery:
                from deliveries.models import DeliveryRequest
                dest_lat = data.get('dest_lat')
                dest_lng = data.get('dest_lng')
                # Destination was already validated (inside campus) before the order was created.
                # Proposal-only: the request enters the shared SEARCHING pool
                # (no pre-assigned rider); every online rider sees it and the
                # first to Accept claims it.
                DeliveryRequest.objects.create(
                    order=order,
                    delivery_location=delivery_location,
                    status=DeliveryRequest.RequestStatus.SEARCHING,
                    assigned_to=None,
                    assigned_at=None,
                    dest_lat=dest_lat,
                    dest_lng=dest_lng,
                )

        return JsonResponse({
            'success': True,
            'order_number': order.order_number,
            'order_id': order.id,
            'is_delivery': is_delivery,
            'delivery_fee': float(order.delivery_fee),
            'total_payment': float(order.total_payment),
            'points_earned': points_earned,
            'new_points': float(user.loyalty_points) if user else 0.0,
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

def check_order_status_api(request, order_num):
    clean_num = order_num.replace('#', '').strip()
    try:
        order = Order.objects.get(order_number__iexact=clean_num)
        return JsonResponse({'exists': True, 'status': order.status})
    except Order.DoesNotExist:
        return JsonResponse({'exists': False})


@require_POST
def submit_feedback_api(request):
    try:
        data = json.loads(request.body)
        order_number = data.get('order_number')
        rating = int(data.get('rating', 5))
        comment = data.get('comment', '')

        order = None
        if order_number:
            clean_num = order_number.replace('#', '').strip()
            order = Order.objects.filter(order_number__iexact=clean_num).first()

        from .models import OrderFeedback
        OrderFeedback.objects.create(
            order=order,
            customer=request.user if request.user.is_authenticated else None,
            rating=rating,
            comment=comment
        )
        return JsonResponse({'success': True, 'message': 'Feedback submitted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
