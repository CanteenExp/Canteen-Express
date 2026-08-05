from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.urls import reverse, NoReverseMatch


# 1. Landing Page & Student Choice
def landing_view(request):
    return render(request, 'accounts/landing.html')


def select_student_role_view(request):
    request.session['user_role'] = 'student'
    request.session['can_deliver'] = False
    kiosk_url = _get_safe_url(['customer_portal:kiosk_menu', 'canteen_menu:kiosk_menu', 'kiosk_menu', '/kiosk/kiosk/'])
    return redirect(kiosk_url if kiosk_url else '/')


# 2. Faculty Onboarding Steps
def faculty_location_view(request):
    if request.method == 'POST':
        lat = request.POST.get('latitude')
        lng = request.POST.get('longitude')
        request.session['user_location'] = {'lat': lat, 'lng': lng}
        return redirect('accounts:faculty_phone')
    
    return render(request, 'accounts/faculty_location.html')


def faculty_phone_view(request):
    if request.method == 'POST':
        phone = request.POST.get('phone_number')
        
        generated_otp = "123456"  # Mock OTP
        request.session['temp_phone'] = phone
        request.session['phone_otp'] = generated_otp
        
        messages.info(request, "OTP sent to your phone number.")
        return redirect('accounts:faculty_verify_phone')

    return render(request, 'accounts/faculty_phone.html')


def faculty_verify_phone_view(request):
    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        saved_otp = request.session.get('phone_otp')

        if entered_otp == saved_otp:
            request.session['phone_verified'] = True
            messages.success(request, "Phone number verified!")
            return redirect('accounts:faculty_register')
        else:
            messages.error(request, "Invalid OTP code. Please try again.")

    return render(request, 'accounts/faculty_verify_phone.html')


def faculty_register_view(request):
    if not request.session.get('phone_verified'):
        messages.warning(request, "Please verify your phone number first.")
        return redirect('accounts:faculty_phone')

    if request.method == 'POST':
        email = request.POST.get('corp_email')
        
        if not email.endswith('.edu.ph'):
            messages.error(request, "Please use a valid corporate / school email address.")
            return render(request, 'accounts/faculty_register.html')

        request.session['temp_reg_data'] = {
            'username': request.POST.get('username'),
            'first_name': request.POST.get('first_name'),
            'last_name': request.POST.get('last_name'),
            'email': email,
            'password': request.POST.get('password'),
            'phone': request.session.get('temp_phone')
        }

        email_otp = "654321"  # Mock OTP
        request.session['email_otp'] = email_otp

        messages.info(request, "OTP sent to your corporate email.")
        return redirect('accounts:faculty_verify_email')

    return render(request, 'accounts/faculty_register.html')


def faculty_verify_email_view(request):
    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        saved_otp = request.session.get('email_otp')

        if entered_otp == saved_otp:
            reg_data = request.session.get('temp_reg_data', {})
            
            username = reg_data.get('username')
            if User.objects.filter(username=username).exists():
                messages.error(request, "Username already exists. Please choose another.")
                return render(request, 'accounts/faculty_register.html')

            user = User.objects.create_user(
                username=reg_data.get('username'),
                email=reg_data.get('email'),
                password=reg_data.get('password'),
                first_name=reg_data.get('first_name', ''),
                last_name=reg_data.get('last_name', '')
            )

            login(request, user)
            
            request.session['user_role'] = 'faculty'
            request.session['can_deliver'] = True

            _clear_registration_sessions(request)

            messages.success(request, f"Welcome, {user.first_name}! Your Faculty account is ready.")
            kiosk_url = _get_safe_url(['customer_portal:kiosk_menu', 'canteen_menu:kiosk_menu', 'kiosk_menu', '/kiosk/kiosk/'])
            return redirect(kiosk_url if kiosk_url else '/')
        else:
            messages.error(request, "Invalid Email OTP code.")

    return render(request, 'accounts/faculty_verify_email.html')


# 3. Standard Login & Logout
def login_view(request):
    if request.user.is_authenticated:
        return redirect(_get_post_login_destination(request.user))

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")

            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)

            return redirect(_get_post_login_destination(user))
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    login_url = _get_safe_url(['accounts:login', 'login', '/accounts/login/'])
    return redirect(login_url if login_url else '/')


# Helper Functions
def _clear_registration_sessions(request):
    keys = ['temp_phone', 'phone_otp', 'phone_verified', 'temp_reg_data', 'email_otp']
    for key in keys:
        if key in request.session:
            del request.session[key]


def _get_post_login_destination(user):
    if user.is_superuser or user.is_staff:
        admin_url = _get_safe_url(['admin:index', 'admin_dashboard:index'])
        if admin_url:
            return admin_url

    candidate_urls = [
        'customer_portal:kiosk_menu',
        'canteen_menu:kiosk_menu',
        'kiosk_menu',
        'accounts:landing',
        '/',
    ]

    destination = _get_safe_url(candidate_urls)
    return destination if destination else '/'


def _get_safe_url(url_candidates):
    for url_name in url_candidates:
        if url_name.startswith('/'):
            return url_name
        try:
            return reverse(url_name)
        except NoReverseMatch:
            continue
    return None