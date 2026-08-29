import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib.auth import get_user_model
from accounts.decorators import role_required

from customer_portal.models import Order 
from canteen_menu.models import MenuItem 
from deliveries.models import DeliveryRequest

User = get_user_model()

@role_required(allowed_roles=['STAFF'])
def staff_dashboard(request):
    """Unified Canteen Staff Dashboard with all management modules."""
    from django.db.models import Sum, Count
    from django.db.models.functions import TruncDate, TruncWeek, TruncMonth

    today = timezone.now().date()
    today_orders = Order.objects.filter(created_at__date=today).exclude(status='unpaid')
    
    total_orders_today = today_orders.count()
    pending_count = Order.objects.filter(status='pending').count()
    preparing_count = Order.objects.filter(status='preparing').count()
    ready_count = Order.objects.filter(status='ready').count()
    
    recent_orders = Order.objects.exclude(status='completed').exclude(status='unpaid').order_by('-created_at')[:5]
    menu_items = MenuItem.objects.all().order_by('name')
    users_list = User.objects.all().order_by('-date_joined')[:30] if hasattr(User, 'date_joined') else User.objects.all()[:30]
    
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
        nutritional_info = request.POST.get('nutritional_info', '')
        
        MenuItem.objects.create(
            name=name,
            price=price,
            stock=stock,
            nutritional_info=nutritional_info,
            is_available=True
        )
        return redirect('kitchen_display:dashboard')

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
    return render(request, 'staff_dashboard.html', context)


@role_required(allowed_roles=['STAFF'])
def kitchen_display(request):
    """Kanban-style Order Board for real-time order processing."""
    kiosk_orders = Order.objects.filter(delivery_info__isnull=True).exclude(status='completed').exclude(status='ready').exclude(status='unpaid').order_by('created_at')
    delivery_orders = Order.objects.filter(delivery_info__isnull=False).exclude(status='completed').exclude(status='ready').order_by('created_at')
    ready_orders = Order.objects.filter(status='ready').order_by('created_at')

    for o in list(kiosk_orders) + list(delivery_orders) + list(ready_orders):
        o.is_delivery = DeliveryRequest.objects.filter(order=o).exists()

    context = {
        'kiosk_orders': kiosk_orders,
        'delivery_orders': delivery_orders,
        'ready_orders': ready_orders,
        'staff_name': request.user.first_name or request.user.username,
    }
    return render(request, 'kitchen_dashboard.html', context)


@role_required(allowed_roles=['STAFF'])
@require_POST
def update_order_status(request, order_id):
    """API endpoint to update order status via AJAX."""
    try:
        data = json.loads(request.body)
        new_status = data.get('status', '').lower()

        order = Order.objects.get(id=order_id)
        order.status = new_status
        order.save()

        return JsonResponse({'success': True, 'message': 'Status updated successfully'})
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Order not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@role_required(allowed_roles=['STAFF'])
def manage_menu(request):
    """View, add, edit, or delete menu items and monitor stock levels."""
    menu_items = MenuItem.objects.all().order_by('name')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        price = request.POST.get('price')
        stock = request.POST.get('stock', 0)
        nutritional_info = request.POST.get('nutritional_info', '')
        is_available = request.POST.get('is_available') == 'on'
        
        MenuItem.objects.create(
            name=name,
            price=price,
            stock=stock,
            nutritional_info=nutritional_info,
            is_available=is_available
        )
        return redirect('kitchen_display:manage_menu')

    context = {'menu_items': menu_items}
    return render(request, 'staff_menu_management.html', context)


@role_required(allowed_roles=['STAFF'])
def toggle_item_availability(request, item_id):
    """Quickly update item availability or stock."""
    item = get_object_or_404(MenuItem, id=item_id)
    item.is_available = not item.is_available
    item.save()
    return redirect('kitchen_display:manage_menu')


@role_required(allowed_roles=['STAFF'])
def admin_pin_verify(request):
    """Prompt staff for a PIN code to access Admin/System governance controls."""
    if request.method == 'POST':
        entered_pin = request.POST.get('pin')
        CORRECT_PIN = '1234'
        
        if entered_pin == CORRECT_PIN:
            request.session['admin_verified'] = True
            return redirect('kitchen_display:admin_governance')
        else:
            return render(request, 'admin_pin_verify.html', {'error': 'Invalid PIN Code. Please try again.'})
            
    return render(request, 'admin_pin_verify.html')


@role_required(allowed_roles=['STAFF'])
def admin_governance(request):
    """Central Governance, User Approvals, and Analytics Dashboard (PIN Protected)."""
    if not request.session.get('admin_verified'):
        return redirect('kitchen_display:admin_pin_verify')
        
    pending_users = User.objects.filter(is_active=False) if hasattr(User, 'is_active') else []
    all_orders = Order.objects.all().order_by('-created_at')[:20]

    context = {
        'pending_users': pending_users,
        'all_orders': all_orders,
    }
    return render(request, 'admin_dashboard.html', context)

@role_required(allowed_roles=['STAFF'])
def admin_logout(request):
    """Exit Admin mode and clear session protection."""
    if 'admin_verified' in request.session:
        del request.session['admin_verified']
    return redirect('kitchen_display:dashboard')