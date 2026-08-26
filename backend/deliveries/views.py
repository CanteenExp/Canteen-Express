# deliveries/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def delivery_dashboard(request):
    # Retrieve active orders pending or in-transit for delivery
    sample_deliveries = [
        {
            'id': 101,
            'customer_name': 'Prof. Juan Dela Cruz',
            'location': 'Building A - Room 302',
            'phone': '09123456789',
            'status': 'Ready for Pick-up',
            'items': '1x Chicken Inasal, 1x Iced Tea',
        },
        {
            'id': 102,
            'customer_name': 'Dr. Maria Santos',
            'location': 'Faculty Lounge - 2nd Floor',
            'phone': '09987654321',
            'status': 'Out for Delivery',
            'items': '2x Pork Sinigang, 2x Rice',
        }
    ]
    
    context = {
        'deliveries': sample_deliveries,
    }
    # Point directly to delivery_dashboard.html inside backend/templates/
    return render(request, 'delivery_dashboard.html', context)


@login_required
def update_delivery_status(request, order_id):
    if request.method == 'POST':
        new_status = request.POST.get('status', 'Accepted')
        # Logic to update Order.status in database goes here
        messages.success(request, f"Order #{order_id} updated to {new_status}.")
    return redirect('deliveries:dashboard')


@login_required
def accept_delivery(request, order_id):
    if request.method == 'POST':
        messages.success(request, f"Order #{order_id} successfully accepted!")
    return redirect('deliveries:dashboard')