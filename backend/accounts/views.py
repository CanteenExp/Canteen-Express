from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect

User = get_user_model()

def landing_view(request):
    return render(request, 'accounts/landing.html')

# STEP 1: Faculty Location Check
@ensure_csrf_cookie
def faculty_location_view(request):
    if request.method == 'POST':
        lat = request.POST.get('latitude')
        lng = request.POST.get('longitude')
        request.session['faculty_lat'] = lat
        request.session['faculty_lng'] = lng
        return redirect('accounts:faculty_auth')
        
    return render(request, 'accounts/faculty_location.html')

# STEP 2: Faculty Auth (Login or Signup with Database Saving & Staff Section Reflection)
@ensure_csrf_cookie
@csrf_protect
def faculty_auth_view(request):
    error = None
    mode = request.GET.get('mode', 'login')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'signup':
            email = request.POST.get('email', '').strip().lower()
            name = request.POST.get('name', '').strip()
            password = request.POST.get('password')
            
            if not email.endswith('@psu.palawan.edu.ph'):
                error = "Institutional email must end with @psu.palawan.edu.ph"
                mode = 'signup'
            elif User.objects.filter(email=email).exists():
                error = "An account with this institutional email already exists. Please sign in."
                mode = 'login'
            else:
                try:
                    username = email.split('@')[0]
                    if User.objects.filter(username=username).exists():
                        username = f"{username}_{User.objects.count()}"
                    
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=name,
                        role='FACULTY',
                        is_email_verified=True
                    )
                    logout(request)
                    login(request, user)
                    request.session['faculty_email'] = email
                    return redirect('accounts:dashboard')
                except Exception as e:
                    error = f"Registration error: {str(e)}"
                    mode = 'signup'
                    
        elif action == 'login':
            email = request.POST.get('email', '').strip().lower()
            password = request.POST.get('password')
            
            try:
                user_obj = User.objects.filter(email=email).first()
                if user_obj:
                    user = authenticate(request, username=user_obj.username, password=password)
                    if user is not None:
                        logout(request)
                        login(request, user)
                        request.session['faculty_email'] = email
                        return redirect('accounts:dashboard')
                    else:
                        error = "Invalid password."
                        mode = 'login'
                else:
                    error = "No account found with this email. Please sign up first."
                    mode = 'signup'
            except Exception as e:
                error = f"Login error: {str(e)}"
                mode = 'login'

    return render(request, 'accounts/faculty_auth.html', {'error': error, 'mode': mode})

# STEP 3: Faculty Dashboard
def faculty_dashboard_view(request):
    from canteen_menu.models import MenuItem, Category
    import json
    menu_items = MenuItem.objects.filter(is_available=True)
    categories = Category.objects.all()
    
    email = request.session.get('faculty_email', '') or getattr(request.user, 'email', '')
    if email:
        local_part = email.split('@')[0]
        name_parts = local_part.replace('.', ' ').replace('_', ' ').split()
        faculty_display_name = ' '.join([p.capitalize() for p in name_parts])
    elif request.user.is_authenticated and request.user.first_name:
        faculty_display_name = request.user.first_name
    else:
        faculty_display_name = 'Professor'

    formatted_menu = []
    for item in menu_items:
        img_url = ''
        if hasattr(item, 'get_image_src'):
            attr = getattr(item, 'get_image_src')
            img_url = attr() if callable(attr) else attr
        elif hasattr(item, 'image') and item.image:
            try:
                img_url = item.image.url
            except ValueError:
                img_url = ''
        category_str = item.category.name if item.category else 'General'
        formatted_menu.append({
            'id': item.id,
            'name': item.name,
            'category': category_str,
            'price': float(item.price) if item.price else 0.0,
            'desc': getattr(item, 'description', ''),
            'badge': getattr(item, 'badge', ''),
            'img': img_url
        })

    from deliveries.models import DeliveryRequest
    if request.user.is_authenticated:
        ongoing_deliveries = DeliveryRequest.objects.filter(order__customer=request.user).exclude(status='DELIVERED').order_by('-requested_at')[:5]
    else:
        ongoing_deliveries = []

    ongoing_data = [{
        'id': d.id,
        'order_number': d.order.order_number,
        'status': d.get_status_display(),
        'raw_status': d.status,
        'location': d.delivery_location,
        'rider_name': d.rider.get_full_name() or d.rider.username if d.rider else 'Searching for Rider...',
        'total_amount': float(d.order.total_amount),
        'created_at': d.requested_at.strftime('%H:%M %p'),
        'items': [{'name': i.item_name, 'qty': i.quantity, 'price': float(i.price)} for i in d.order.items.all()]
    } for d in ongoing_deliveries]

    context = {
        'menu_items': menu_items,
        'categories': categories,
        'menu_data_json': json.dumps(formatted_menu),
        'faculty_display_name': faculty_display_name,
        'ongoing_deliveries_json': json.dumps(ongoing_data)
    }
    return render(request, 'accounts/dashboard.html', context)


# Separate Staff Login View
@ensure_csrf_cookie
@csrf_protect
def staff_login_view(request):
    if request.method == 'GET':
        logout(request)
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None and (user.is_staff or getattr(user, 'role', '') in ['STAFF', 'ADMIN']):
            logout(request)
            login(request, user)
            return redirect('canteen_menu:staff_dashboard')
        else:
            error = "Invalid canteen staff credentials."
    return render(request, 'accounts/staff_login.html', {'error': error})


# Separate Delivery Personnel Login View
@ensure_csrf_cookie
@csrf_protect
def delivery_login_view(request):
    if request.method == 'GET':
        logout(request)
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None and (getattr(user, 'role', '') == 'DELIVERY' or user.is_staff):
            logout(request)
            login(request, user)
            return redirect('deliveries:dashboard')
        else:
            error = "Invalid delivery personnel credentials."
    return render(request, 'accounts/delivery_login.html', {'error': error})


# Role-specific Logout Views
def faculty_logout_view(request):
    request.session.flush()
    logout(request)
    return redirect('accounts:landing')

def staff_logout_view(request):
    logout(request)
    return redirect('accounts:staff_login')

def delivery_logout_view(request):
    logout(request)
    return redirect('accounts:delivery_login')
