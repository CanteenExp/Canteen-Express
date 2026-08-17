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


# 2. STAFF SIDE - Add New Item (CREATE)
def staff_menu_create(request):
    if request.method == 'POST':
        form = MenuItemForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Bagong pagkain ay matagumpay na naidagdag!")
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

def staff_dashboard(request):
    # Kukuha ng parehong Data (Orders & Menu Items) para sa iisang page
    context = {
        'items': [], # Menu items query
        'incoming_orders': [], # Incoming orders query
        'preparing_orders': [], # Preparing orders query
        'ready_orders': [], # Ready orders query
    }
    return render(request, 'canteen_menu/staff_dashboard.html', context)

@csrf_exempt
def process_barcode_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        order_id = data.get('order_id')
        
        # Halimbawa: Update status sa database
        # order = Order.objects.get(order_number=order_id)
        # order.status = 'PREPARING'
        # order.is_paid = True
        # order.save()

        return JsonResponse({
            'status': 'success',
            'message': f'Order {order_id} verified and moved to kitchen.'
        })
    return JsonResponse({'status': 'error'}, status=400)


def counter_pos_view(request):
    return render(request, 'canteen_menu/counter_pos.html')