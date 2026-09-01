import json
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
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
    return redirect(reverse('canteen_menu:staff_dashboard') + '?tab=menu')

def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated successfully!")
    return redirect(reverse('canteen_menu:staff_dashboard') + '?tab=menu')

def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.delete()
        messages.success(request, "Category deleted successfully!")
    return redirect(reverse('canteen_menu:staff_dashboard') + '?tab=menu')


import os
import shutil
import urllib.parse
from django.conf import settings
from django.utils.text import slugify

def _auto_sync_menu_image(item):
    """
    Auto-syncs menu image from designated local folders matching item name (instant check without listing large dirs).
    """
    if item.image:
        return  # Manually uploaded image takes precedence

    slug_name = slugify(item.name)
    clean_name = item.name.lower().replace(' ', '_').replace('-', '_')
    no_space_name = item.name.lower().replace(' ', '')
    raw_name = item.name.lower()

    candidates = [slug_name, clean_name, no_space_name, raw_name, item.name]
    extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']

    media_menu_dir = os.path.join(settings.MEDIA_ROOT, 'menu_items')
    os.makedirs(media_menu_dir, exist_ok=True)

    source_dirs = [
        media_menu_dir,
        "C:/Users/vince/Vince Projects/CAPSTONE PROJECT/CANTEEN EXPRESS GITHUB MERGE/TESTING/backend/media/menu_items",
        "C:/Users/vince/Vince Projects/CAPSTONE PROJECT/CANTEEN EXPRESS GITHUB MERGE/TESTING/Biscuits & Beverages",
        "C:/Users/vince/Vince Projects/CAPSTONE PROJECT/CANTEEN EXPRESS GITHUB MERGE/TESTING/Meryenda",
        "C:/Users/vince/Vince Projects/CAPSTONE PROJECT/CANTEEN EXPRESS GITHUB MERGE/TESTING/Ulams",
    ]

    for s_dir in source_dirs:
        if os.path.exists(s_dir):
            for cand in candidates:
                for ext in extensions:
                    filename = f"{cand}{ext}"
                    src_path = os.path.join(s_dir, filename)
                    if os.path.exists(src_path):
                        target_path = os.path.join(media_menu_dir, filename)
                        if not os.path.exists(target_path) and os.path.abspath(src_path) != os.path.abspath(target_path):
                            try:
                                shutil.copy2(src_path, target_path)
                            except Exception:
                                pass
                        item.image = f'menu_items/{filename}'
                        item.image_url = ''
                        return

    # Automated API Food Photo Fallback matching item name
    encoded_query = urllib.parse.quote(f"{item.name},food,dish,filipino food")
    item.image_url = f"https://loremflickr.com/600/400/{encoded_query}"


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
            _auto_sync_menu_image(item)
            item.save()
            messages.success(request, f"Ang menu na '{item.name}' ay matagumpay na naidagdag na may auto-synced image!")
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
    return redirect(reverse('canteen_menu:staff_dashboard') + '?tab=menu')

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

    # Audit Logs & Reports Data
    from customer_portal.models import OrderItem
    audit_logs = []
    for o in Order.objects.all().order_by('-created_at')[:15]:
        audit_logs.append({
            'timestamp': o.created_at,
            'action': f"Order {o.order_number} ({o.status}) - ₱{o.total_amount}",
            'user': o.customer.username if o.customer else 'Guest / Walk-in',
            'type': 'ORDER'
        })
    for u in User.objects.all().order_by('-date_joined')[:10]:
        audit_logs.append({
            'timestamp': u.date_joined if hasattr(u, 'date_joined') else timezone.now(),
            'action': f"User account registered: {u.username} ({getattr(u, 'role', 'STUDENT')})",
            'user': u.username,
            'type': 'USER'
        })
    audit_logs = sorted(audit_logs, key=lambda x: x['timestamp'], reverse=True)[:20]

    # Category Sales for Pie Chart
    pie_labels = []
    pie_data = []
    for cat in Category.objects.all():
        cat_items = cat.menu_items.values_list('name', flat=True)
        cat_rev = OrderItem.objects.filter(order__status__in=['ready', 'completed'], item_name__in=cat_items).aggregate(total=Sum('price'))['total'] or 0
        if cat_rev > 0:
            pie_labels.append(cat.name)
            pie_data.append(float(cat_rev))
    if not pie_labels:
        pie_labels = ['General Meals']
        pie_data = [float(sales_today or 100)]

    pie_chart_data = {'labels': pie_labels, 'data': pie_data}
    line_chart_data = {
        'labels': daily_chart_data['labels'],
        'data': [row['count'] for row in reversed(daily_sales)] if daily_sales else [1, 2, 3]
    }

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
        
        item = MenuItem(
            name=name,
            category=category,
            price=price,
            stock=stock,
            image_url=image_url,
            image=image,
            description=description,
            is_available=True
        )
        _auto_sync_menu_image(item)
        item.save()
        messages.success(request, "New menu item added successfully with auto-synced image!")
        return redirect(reverse('canteen_menu:staff_dashboard') + '?tab=menu')

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
        'audit_logs': audit_logs,
        'pie_chart_data': pie_chart_data,
        'line_chart_data': line_chart_data,
        'pie_chart_data_json': json.dumps(pie_chart_data),
        'line_chart_data_json': json.dumps(line_chart_data),
    }
    return render(request, 'canteen_menu/staff_dashboard.html', context)


@role_required(allowed_roles=['STAFF', 'ADMIN'])
def export_report_view(request, format_type):
    from django.http import HttpResponse
    from customer_portal.models import Order
    from django.utils import timezone
    
    valid_orders = Order.objects.filter(status__in=['ready', 'completed'])
    total_rev = valid_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    total_count = valid_orders.count()
    
    if format_type == 'excel':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="canteen_overall_sales_report.csv"'
        response.write("Canteen Express - Overall Sales & Financial Report\n")
        response.write(f"Generated On,{timezone.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        response.write(f"Total Completed/Ready Orders,{total_count}\n")
        response.write(f"Total Revenue (PHP),{total_rev:.2f}\n\n")
        response.write("Order ID,Customer,Total Amount,Status,Date\n")
        for o in valid_orders.order_by('-created_at'):
            cust = o.customer.username if o.customer else 'Guest'
            response.write(f"{o.order_number},{cust},{o.total_amount},{o.status},{o.created_at.strftime('%Y-%m-%d %H:%M')}\n")
        return response

    elif format_type == 'docx':
        html_content = f"""
        <html>
        <head><meta charset="utf-8"><title>Canteen Express Overall Report</title></head>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h1 style="color: #FF6117; text-align: center;">Canteen Express - Overall Report</h1>
            <p style="text-align: center; color: #666;">Generated on {timezone.now().strftime('%B %d, %Y %H:%M')}</p>
            <hr/>
            <h2>Executive Summary</h2>
            <p><strong>Total Revenue:</strong> ₱{total_rev:,.2f}</p>
            <p><strong>Total Completed Orders:</strong> {total_count}</p>
            <hr/>
            <h2>Recent Completed/Ready Orders</h2>
            <table border="1" cellpadding="8" cellspacing="0" style="width:100%; border-collapse: collapse;">
                <tr style="background-color: #f2f2f2;"><th>Order #</th><th>Customer</th><th>Amount</th><th>Status</th><th>Date</th></tr>
        """
        for o in valid_orders.order_by('-created_at')[:50]:
            cust = o.customer.username if o.customer else 'Guest'
            html_content += f"<tr><td>{o.order_number}</td><td>{cust}</td><td>₱{o.total_amount:,.2f}</td><td>{o.status}</td><td>{o.created_at.strftime('%Y-%m-%d %H:%M')}</td></tr>"
        html_content += "</table></body></html>"
        
        response = HttpResponse(html_content, content_type='application/msword')
        response['Content-Disposition'] = 'attachment; filename="canteen_overall_report.doc"'
        return response

    elif format_type == 'pdf':
        html_content = f"""
        <html>
        <head><meta charset="utf-8"><title>Canteen Express Overall Report PDF</title></head>
        <body style="font-family: Helvetica, Arial, sans-serif; padding: 30px; color: #333;">
            <div style="text-align: center; margin-bottom: 20px;">
                <h1 style="color: #FF6117; margin: 0;">CANTEEN EXPRESS</h1>
                <p style="font-size: 14px; color: #555; margin: 5px 0;">Official Overall Sales & Analytics Report</p>
                <p style="font-size: 11px; color: #888;">Generated on {timezone.now().strftime('%B %d, %Y %H:%M')}</p>
            </div>
            <hr style="border: 1px solid #ddd; margin-bottom: 20px;"/>
            <div style="background: #f9f9f9; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <h3 style="margin-top: 0; color: #111;">Summary Metrics</h3>
                <p><strong>Total Revenue:</strong> ₱{total_rev:,.2f}</p>
                <p><strong>Total Successful Orders:</strong> {total_count}</p>
            </div>
            <h3>Detailed Orders List</h3>
            <table border="1" cellpadding="6" cellspacing="0" style="width:100%; border-collapse: collapse; font-size: 12px;">
                <tr style="background-color: #333; color: white;"><th>Order #</th><th>Customer</th><th>Amount</th><th>Status</th><th>Date</th></tr>
        """
        for o in valid_orders.order_by('-created_at')[:50]:
            cust = o.customer.username if o.customer else 'Guest'
            html_content += f"<tr><td>{o.order_number}</td><td>{cust}</td><td>₱{o.total_amount:,.2f}</td><td>{o.status}</td><td>{o.created_at.strftime('%Y-%m-%d %H:%M')}</td></tr>"
        html_content += """
            </table>
            <script>window.onload = function() { window.print(); }</script>
        </body></html>
        """
        response = HttpResponse(html_content, content_type='text/html')
        return response

    return redirect('canteen_menu:staff_dashboard')

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
            if request.POST.get('description') is not None:
                item.description = request.POST.get('description')
            category_id = request.POST.get('category')
            if category_id:
                item.category = get_object_or_404(Category, pk=category_id)
            if request.POST.get('image_url'):
                item.image_url = request.POST.get('image_url')
            if request.FILES.get('image'):
                item.image = request.FILES.get('image')
            
            if not item.image and not item.image_url:
                _auto_sync_menu_image(item)
            item.save()
            messages.success(request, f"Updated {item.name} successfully!")
        except Exception as e:
            messages.error(request, f"Error updating item: {str(e)}")
    return redirect(reverse('canteen_menu:staff_dashboard') + '?tab=menu')

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
    return redirect(reverse('canteen_menu:staff_dashboard') + '?tab=deliveries')

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
    return redirect(reverse('canteen_menu:staff_dashboard') + '?tab=deliveries')

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
    return redirect(reverse('canteen_menu:staff_dashboard') + '?tab=users')

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
