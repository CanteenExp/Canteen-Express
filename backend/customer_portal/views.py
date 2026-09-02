import json
import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from canteen_menu.models import MenuItem
from .models import Order, OrderItem


# Helper function to format active DB menu items for Kiosk JSON
def _get_formatted_menu():
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
        total_amount = data.get('total_amount', 0)
        is_delivery = data.get('is_delivery', False)
        delivery_location = data.get('delivery_location', 'Faculty Office Building')

        if not cart_items:
            return JsonResponse({'success': False, 'message': 'Cart is empty.'}, status=400)

        # Campus-only scope: validate delivery destination BEFORE creating the order.
        # If the customer's location (GPS or building preset) falls outside the PSU
        # campus geofence, the whole order is rejected.
        if is_delivery:
            from deliveries.utils import is_within_campus
            dest_lat = data.get('dest_lat')
            dest_lng = data.get('dest_lng')
            if not is_within_campus(dest_lat, dest_lng):
                return JsonResponse({
                    'success': False,
                    'message': 'Delivery is only available within the Palawan State University campus. Please make sure your location is inside the campus and try again.'
                }, status=422)

        order_number = f"#CE-{random.randint(1000, 9999)}"
        initial_status = 'pending' if is_delivery else 'unpaid'
        delivery_fee = 30.00 if is_delivery else 0.00

        order = Order.objects.create(
            order_number=order_number,
            total_amount=total_amount,
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
            DeliveryRequest.objects.create(
                order=order,
                delivery_location=delivery_location,
                status=DeliveryRequest.RequestStatus.SEARCHING,
                dest_lat=dest_lat,
                dest_lng=dest_lng,
            )

        return JsonResponse({
            'success': True,
            'order_number': order.order_number,
            'order_id': order.id,
            'is_delivery': is_delivery
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)