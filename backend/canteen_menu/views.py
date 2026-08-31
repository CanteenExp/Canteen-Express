import json
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import MenuItem, Category
from django.views.decorators.csrf import csrf_exempt

try:
    from .forms import MenuItemForm, CategoryForm
except ImportError:
    from customer_portal.forms import MenuItemForm
    CategoryForm = None


# 1. STAFF SIDE - List all food items (READ) & Categories
def staff_menu_list(request):
    items = MenuItem.objects.all().order_by('category__name', 'name')
    categories = Category.objects.all().order_by('name')
    return render(request, 'canteen_menu/menu_list.html', {'items': items, 'categories': categories})


def staff_menu_toggle_availability(request, pk):
    item = get_object_or_404(MenuItem, pk=pk)
    item.is_available = not item.is_available
    item.save()
    messages.success(request, f"Updated availability for {item.name}")
    return redirect('canteen_menu:staff_menu_list')


# Category CRUD Views
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "New category added successfully!")
            return redirect('canteen_menu:staff_dashboard')
    else:
        form = CategoryForm()
    return render(request, 'canteen_menu/category_form.html', {'form': form, 'action_title': 'Add New Category'})

def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated successfully!")
            return redirect('canteen_menu:staff_dashboard')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'canteen_menu/category_form.html', {'form': form, 'action_title': 'Edit Category', 'category': category})

def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.delete()
        messages.success(request, "Category deleted successfully!")
        return redirect('canteen_menu:staff_dashboard')
    return render(request, 'canteen_menu/category_confirm_delete.html', {'category': category})


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
    from customer_portal.models import Order
    from django.utils import timezone
    incoming_orders = Order.objects.filter(status='pending').order_by('created_at')
    preparing_orders = Order.objects.filter(status='preparing').order_by('created_at')
    ready_orders = Order.objects.filter(status='ready').order_by('created_at')
    today = timezone.now().date()
    done_today_count = Order.objects.filter(status='completed', created_at__date=today).count()
    context = {
        'incoming_orders': incoming_orders,
        'preparing_orders': preparing_orders,
        'ready_orders': ready_orders,
        'done_today_count': done_today_count,
    }
    return render(request, 'canteen_menu/counter_board.html', context)

from accounts.decorators import role_required

@role_required(allowed_roles=['STAFF', 'ADMIN'])
def staff_dashboard(request):
    from django.utils import timezone
    from customer_portal.models import Order
    from deliveries.models import DeliveryRequest
    from django.db.models import Sum, Count
    from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
    from django.contrib.auth import get_user_model
    User = get_user_model()

    today = timezone.now().date()
    today_orders = Order.objects.filter(created_at__date=today).exclude(status='unpaid')
    
    total_orders_today = today_orders.count()
    pending_count = Order.objects.filter(status='pending').count()
    preparing_count = Order.objects.filter(status='preparing').count()
    ready_count = Order.objects.filter(status='ready').count()
    
    recent_orders = Order.objects.exclude(status='completed').exclude(status='unpaid').order_by('-created_at')[:5]
    menu_items = MenuItem.objects.all().order_by('category__name', 'name')
    categories = Category.objects.all().order_by('name')
    users_list = User.objects.exclude(role='DELIVERY').order_by('-date_joined')[:30] if hasattr(User, 'date_joined') else User.objects.exclude(role='DELIVERY')[:30]
    delivery_staff_list = User.objects.filter(role='DELIVERY')
    
    try:
        delivery_requests = DeliveryRequest.objects.all().order_by('-requested_at')[:20]
    except Exception:
        delivery_requests = []

    # Sales Reports & Analytics
    valid_orders = Order.objects.filter(status__in=['ready', 'completed'])
    
    daily_sales = list(
        valid_orders
        .annotate(period=TruncDate('created_at'))
        .values('period')
        .annotate(total=Sum('total_amount'), count=Count('id'))
        .order_by('-period')[:7]
    )
    
    weekly_sales = list(
        valid_orders
        .annotate(period=TruncWeek('created_at'))
        .values('period')
        .annotate(total=Sum('total_amount'), count=Count('id'))
        .order_by('-period')[:4]
    )
    
    monthly_sales = list(
        valid_orders
        .annotate(period=TruncMonth('created_at'))
        .values('period')
        .annotate(total=Sum('total_amount'), count=Count('id'))
        .order_by('-period')[:6]
    )

    daily_chart_data = {
        'labels': [row['period'].strftime('%b %d') if row['period'] else '' for row in reversed(daily_sales)],
        'data': [float(row['total']) if row['total'] else 0.0 for row in reversed(daily_sales)],
    }
    weekly_chart_data = {
        'labels': [f"Week of {row['period'].strftime('%b %d')}" if row['period'] else '' for row in reversed(weekly_sales)],
        'data': [float(row['total']) if row['total'] else 0.0 for row in reversed(weekly_sales)],
    }
    monthly_chart_data = {
        'labels': [row['period'].strftime('%b %Y') if row['period'] else '' for row in reversed(monthly_sales)],
        'data': [float(row['total']) if row['total'] else 0.0 for row in reversed(monthly_sales)],
    }

    sales_today = valid_orders.filter(created_at__date=today).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    week_start = today - timezone.timedelta(days=7)
    sales_week = valid_orders.filter(created_at__date__gte=week_start).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    month_start = today.replace(day=1)
    sales_month = valid_orders.filter(created_at__date__gte=month_start).aggregate(Sum('total_amount'))['total_amount__sum'] or 0

    if request.method == 'POST' and 'add_menu_item' in request.POST:
        name = request.POST.get('name')
        price = request.POST.get('price')
        stock = request.POST.get('stock', 50)
        category_id = request.POST.get('category')
        category = get_object_or_404(Category, id=category_id) if category_id else Category.objects.first()
        image_url = request.POST.get('image_url', '')
        image = request.FILES.get('image')
        description = request.POST.get('description', '')
        if not description:
            description = _generate_auto_desc(name)
        
        MenuItem.objects.create(
            name=name,
            category=category,
            price=price,
            stock=stock,
            image_url=image_url,
            image=image,
            description=description,
            is_available=True
        )
        messages.success(request, "New menu item added successfully!")
        return redirect('canteen_menu:staff_dashboard')

    staff_name = request.user.first_name if request.user.is_authenticated and request.user.first_name else (request.user.username if request.user.is_authenticated else 'Staff')

    context = {
        'total_orders_today': total_orders_today,
        'pending_count': pending_count,
        'preparing_count': preparing_count,
        'ready_count': ready_count,
        'recent_orders': recent_orders,
        'menu_items': menu_items,
        'categories': categories,
        'users_list': users_list,
        'delivery_staff_list': delivery_staff_list,
        'delivery_requests': delivery_requests,
        'staff_name': staff_name,
        'daily_sales': daily_sales,
        'weekly_sales': weekly_sales,
        'monthly_sales': monthly_sales,
        'daily_chart_data': daily_chart_data,
        'weekly_chart_data': weekly_chart_data,
        'monthly_chart_data': monthly_chart_data,
        'sales_today': sales_today,
        'sales_week': sales_week,
        'sales_month': sales_month,
    }
    return render(request, 'canteen_menu/staff_dashboard.html', context)

@role_required(allowed_roles=['STAFF', 'ADMIN'])
def staff_menu_toggle_ajax(request, pk):
    item = get_object_or_404(MenuItem, pk=pk)
    item.is_available = not item.is_available
    item.save()
    return JsonResponse({'success': True, 'is_available': item.is_available, 'stock': item.stock})

@role_required(allowed_roles=['STAFF', 'ADMIN'])
def staff_menu_edit_ajax(request):
    if request.method == 'POST':
        try:
            item_id = request.POST.get('item_id')
            item = get_object_or_404(MenuItem, pk=item_id)
            item.name = request.POST.get('name', item.name)
            item.price = request.POST.get('price', item.price)
            item.stock = request.POST.get('stock', item.stock)
            category_id = request.POST.get('category')
            if category_id:
                item.category = get_object_or_404(Category, pk=category_id)
            if request.POST.get('image_url'):
                item.image_url = request.POST.get('image_url')
            if request.FILES.get('image'):
                item.image = request.FILES.get('image')
            item.save()
            messages.success(request, f"Updated {item.name} successfully!")
        except Exception as e:
            messages.error(request, f"Error updating item: {str(e)}")
    return redirect('canteen_menu:staff_dashboard')

@role_required(allowed_roles=['STAFF', 'ADMIN'])
def create_delivery_staff_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        phone = request.POST.get('phone')
        vehicle_plate = request.POST.get('vehicle_plate')
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
        else:
            User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=request.POST.get('first_name', 'Rider'),
                role='DELIVERY',
                phone=phone,
                vehicle_plate=vehicle_plate,
                account_status='active'
            )
            messages.success(request, f"Delivery staff {username} created successfully!")
    return redirect('canteen_menu:staff_dashboard')

@role_required(allowed_roles=['STAFF', 'ADMIN'])
def update_delivery_staff_status_view(request, pk):
    if request.method == 'POST':
        from django.contrib.auth import get_user_model
        User = get_user_model()
        rider = get_object_or_404(User, pk=pk, role='DELIVERY')
        action = request.POST.get('action')
        if action == 'hold':
            rider.account_status = 'held'
            rider.is_active = False
            messages.success(request, f"Rider {rider.username} account held.")
        elif action == 'penalize':
            rider.account_status = 'penalized'
            messages.success(request, f"Rider {rider.username} penalized.")
        elif action == 'toggle_active':
            rider.is_active = not rider.is_active
            rider.account_status = 'active' if rider.is_active else 'inactive'
            messages.success(request, f"Rider {rider.username} status toggled.")
        rider.save()
    return redirect('canteen_menu:staff_dashboard')

@role_required(allowed_roles=['STAFF', 'ADMIN'])
def update_user_status_view(request, pk):
    if request.method == 'POST':
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = get_object_or_404(User, pk=pk)
        action = request.POST.get('action')
        if action == 'ban':
            user.is_active = False
            user.account_status = 'banned'
            messages.success(request, f"User {user.username} banned.")
        elif action == 'restrict':
            user.account_status = 'restricted'
            messages.success(request, f"User {user.username} restricted.")
        elif action == 'activate':
            user.is_active = True
            user.account_status = 'active'
            messages.success(request, f"User {user.username} activated.")
        user.save()
    return redirect('canteen_menu:staff_dashboard')

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
<<<<<<< HEAD
    return render(request, 'canteen_menu/counter_pos.html')
=======
    return render(request, 'canteen_menu/counter_pos.html')
>>>>>>> pilot-testing
