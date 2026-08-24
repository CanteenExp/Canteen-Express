import json
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import MenuItem
from django.views.decorators.csrf import csrf_exempt

try:
    from .forms import MenuItemForm
except ImportError:
    from customer_portal.forms import MenuItemForm


# 1. STAFF SIDE - List all food items (READ)
def staff_menu_list(request):
    items = MenuItem.objects.all().order_by('-id') 
    return render(request, 'canteen_menu/menu_list.html', {'items': items})


def _generate_auto_desc(name):
    name_lower = name.lower()
    if 'turon' in name_lower or 'banana' in name_lower or 'meryenda' in name_lower:
        return f"Crispy and sweet golden {name}, freshly fried and glazed for the ultimate campus snack."
    elif 'pork' in name_lower or 'chicken' in name_lower or 'beef' in name_lower or 'rice' in name_lower:
        return f"Savory and hearty {name} served piping hot, rich in protein, flavor, and cooked with authentic canteen recipe."
    elif 'coke' in name_lower or 'sprite' in name_lower or 'beverage' in name_lower or 'juice' in name_lower:
        return f"Ice-cold refreshing {name} to complement your meal."
    return f"Freshly prepared {name}, cooked daily with quality ingredients."


# 2. STAFF SIDE - Add New Item (CREATE)
def staff_menu_create(request):
    if request.method == 'POST':
        form = MenuItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            if not item.description:
                item.description = _generate_auto_desc(item.name)
            item.save()
            messages.success(request, "Bagong pagkain ay matagumpay na naidagdag na may automated description!")
            return redirect('canteen_menu:staff_menu_list')
        else:
            messages.error(request, "May mali sa mga impormasyong inilagay. Paki-ayos ang mga fields na may error.")
    else:
        form = MenuItemForm()
        
    return render(request, 'canteen_menu/menu_form.html', {'form': form, 'action_title': 'Add New Menu Item'})


# 3. STAFF SIDE - Edit Item (UPDATE)
def staff_menu_update(request, pk):
    item = get_object_or_404(MenuItem, pk=pk)
    if request.method == 'POST':
        form = MenuItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Nabaguhan na ang detalye ng pagkain!")
            return redirect('canteen_menu:staff_menu_list')
        else:
            messages.error(request, "May mali sa pag-update ng item. Paki-check ang form.")
    else:
        form = MenuItemForm(instance=item)
        
    return render(request, 'canteen_menu/menu_form.html', {'form': form, 'action_title': 'Edit Menu Item', 'item': item})


# 4. STAFF SIDE - Delete Item (DELETE)
def staff_menu_delete(request, pk):
    item = get_object_or_404(MenuItem, pk=pk)
    if request.method == 'POST':
        item.delete()
        messages.success(request, "Naipagbura na ang item!")
        return redirect('canteen_menu:staff_menu_list')
    return render(request, 'canteen_menu/menu_confirm_delete.html', {'item': item})

def counter_board(request):
    # Dito pwedeng kumuha ng Order data mula sa database
    return render(request, 'canteen_menu/counter_board.html')

from accounts.decorators import role_required

@role_required(allowed_roles=['STAFF', 'ADMIN'])
def staff_dashboard(request):
    from django.utils import timezone
    from customer_portal.models import Order
    from deliveries.models import DeliveryRequest
    from django.contrib.auth import get_user_model
    User = get_user_model()

    today = timezone.now().date()
    today_orders = Order.objects.filter(created_at__date=today)
    
    total_orders_today = today_orders.count()
    pending_count = Order.objects.filter(status='pending').count()
    preparing_count = Order.objects.filter(status='preparing').count()
    ready_count = Order.objects.filter(status='ready').count()
    
    recent_orders = Order.objects.exclude(status='completed').order_by('-created_at')[:5]
    menu_items = MenuItem.objects.all().order_by('name')
    users_list = User.objects.all().order_by('-date_joined')[:30] if hasattr(User, 'date_joined') else User.objects.all()[:30]
    
    try:
        delivery_requests = DeliveryRequest.objects.all().order_by('-requested_at')[:20]
    except Exception:
        delivery_requests = []

    if request.method == 'POST' and 'add_menu_item' in request.POST:
        name = request.POST.get('name')
        price = request.POST.get('price')
        stock = request.POST.get('stock', 50)
        nutritional_info = request.POST.get('nutritional_info', '')
        
        MenuItem.objects.create(
            name=name,
            price=price,
            stock=stock,
            nutritional_info=nutritional_info,
            is_available=True
        )
        return redirect('canteen_menu:staff_dashboard')

    staff_name = request.user.first_name if request.user.is_authenticated and request.user.first_name else (request.user.username if request.user.is_authenticated else 'Staff')

    context = {
        'total_orders_today': total_orders_today,
        'pending_count': pending_count,
        'preparing_count': preparing_count,
        'ready_count': ready_count,
        'recent_orders': recent_orders,
        'menu_items': menu_items,
        'users_list': users_list,
        'delivery_requests': delivery_requests,
        'staff_name': staff_name,
    }
    return render(request, 'canteen_menu/staff_dashboard.html', context)

@csrf_exempt
def process_barcode_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON body'}, status=400)
            
        action = data.get('action', 'fetch')
        raw_order_id = str(data.get('order_id', '')).strip()

        if not raw_order_id:
            return JsonResponse({'status': 'error', 'message': 'Order ID missing'}, status=400)

        # Try to find order in customer_portal
        from customer_portal.models import Order as KioskOrder

        clean_code = raw_order_id.replace('#', '').strip()
        possible_numbers = [
            raw_order_id,
            clean_code,
            f"#{clean_code}",
            f"CE-{clean_code}" if not clean_code.startswith("CE-") else clean_code,
            f"#CE-{clean_code.replace('CE-', '')}"
        ]

        order = None
        for p_num in possible_numbers:
            try:
                order = KioskOrder.objects.get(order_number__iexact=p_num)
                if order:
                    break
            except KioskOrder.DoesNotExist:
                continue

        if not order:
            return JsonResponse({'status': 'error', 'message': f'Queue Slip #{clean_code} not found or already processed!'}, status=404)

        if action == 'confirm_payment':
            order.status = 'pending'
            order.save()
            return JsonResponse({
                'status': 'success',
                'message': f'Order {order.order_number} verified and moved to kitchen board.'
            })

        # Fetch order details
        items = []
        for item in order.items.all():
            items.append({
                'name': item.item_name,
                'qty': item.quantity,
                'price': float(item.price)
            })

        order_id_clean = order.order_number.replace('#', '')

        return JsonResponse({
            'status': 'success',
            'order': {
                'orderId': order_id_clean,
                'orderNumber': order.order_number,
                'type': 'DINE-IN',
                'status': order.status,
                'total': float(order.total_amount),
                'items': items
            }
        })

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


def counter_pos_view(request):
    return render(request, 'canteen_menu/counter_pos.html')