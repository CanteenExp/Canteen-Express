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

        if not cart_items:
            return JsonResponse({'success': False, 'message': 'Walang laman ang cart.'}, status=400)

        order_number = f"#CE-{random.randint(1000, 9999)}"

        order = Order.objects.create(
            order_number=order_number,
            total_amount=total_amount,
            status='pending'
        )

        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                item_name=item.get('name', ''),
                price=item.get('price', 0),
                quantity=item.get('qty', 1)
            )

        return JsonResponse({
            'success': True,
            'order_number': order.order_number,
            'order_id': order.id
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)