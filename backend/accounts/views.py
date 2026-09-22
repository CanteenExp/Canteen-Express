from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.http import JsonResponse
import random
import json
import os
import re
import time
from django.core.mail import send_mail

User = get_user_model()

def is_strong_password(password):
    if len(password) < 6:
        return False
    return True

def _otp_rate_allowed(session, prefix, limit=5, window=600, cooldown=60):
    now = int(time.time())
    last = session.get(f'{prefix}_sent_at', 0)
    count = session.get(f'{prefix}_sent_count', 0)
    if now - last < cooldown:
        return 'cooldown'
    if now - last >= window:
        session[f'{prefix}_sent_at'] = now
        session[f'{prefix}_sent_count'] = 1
        return ''
    if count >= limit:
        return 'limit'
    session[f'{prefix}_sent_at'] = now
    session[f'{prefix}_sent_count'] = count + 1
    return ''

def landing_view(request):
    return render(request, 'accounts/landing.html')


def access_denied_view(request):
    """Shown when a logged-in user opens a page meant for a different role."""
    user_role = getattr(request.user, 'role', '')
    portal_url = 'customer_portal:kiosk_menu'
    login_url = 'accounts:landing'

    if user_role in ('STAFF', 'ADMIN') or request.user.is_staff:
        portal_url = 'canteen_menu:staff_dashboard'
        login_url = 'accounts:staff_login'
    elif user_role in ('DELIVERY', 'RIDER'):
        portal_url = 'deliveries:dashboard'
        login_url = 'accounts:delivery_login'
    elif user_role == 'FACULTY':
        portal_url = 'accounts:dashboard'
        login_url = 'accounts:faculty_auth'
    elif user_role == 'STUDENT':
        portal_url = 'customer_portal:kiosk_menu'
        login_url = 'accounts:landing'

    return render(request, 'accounts/access_denied.html', {'portal_url': portal_url, 'login_url': login_url})

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
            if request.POST.get('website'):
                return redirect('accounts:landing')
            email = request.POST.get('email', '').strip().lower()
            name = request.POST.get('name', '').strip()
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')
            
            if not email.endswith('@psu.palawan.edu.ph'):
                error = "Institutional email must end with @psu.palawan.edu.ph"
                mode = 'signup'
            elif not email.split('@')[0] or email.split('@')[0].isdigit() or not any(c.isalpha() for c in email.split('@')[0]):
                error = "Institutional email cannot consist solely of numbers. It must contain letters before @psu.palawan.edu.ph."
                mode = 'signup'
            elif password != confirm_password:
                error = "Passwords do not match."
                mode = 'signup'
            elif not is_strong_password(password):
                error = "Password must be at least 6 characters."
                mode = 'signup'
            elif not request.session.get('otp_verified') or request.session.get('signup_email') != email:
                error = "Please verify your email with the OTP code first."
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
            remember_me = request.POST.get('remember_me')
            
            try:
                user_obj = User.objects.filter(email=email).first()
                if user_obj:
                    user = authenticate(request, username=user_obj.username, password=password)
                    if user is not None:
                        logout(request)
                        login(request, user)
                        if remember_me:
                            request.session.set_expiry(1209600)
                        else:
                            request.session.set_expiry(0)
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
def faculty_dashboard_view(request, token=None):
    if not request.user.is_authenticated:
        return redirect('accounts:faculty_auth')
    user_role = getattr(request.user, 'role', '')
    if user_role not in ('FACULTY', 'STAFF', 'ADMIN') and not request.user.is_staff and not request.user.is_superuser:
        return redirect('accounts:access_denied')

    import uuid
    from django.urls import reverse
    session_token = request.session.get('faculty_secure_token')
    if not session_token:
        session_token = uuid.uuid4().hex[:12]
        request.session['faculty_secure_token'] = session_token

    if not token or token != session_token:
        query_string = request.META.get('QUERY_STRING', '')
        redirect_url = reverse('accounts:dashboard_hashed', kwargs={'token': session_token})
        if query_string:
            redirect_url += f'?{query_string}'
        return redirect(redirect_url)

    from canteen_menu.models import MenuItem, Category
    import json
    menu_items = MenuItem.objects.filter(is_available=True)
    categories = Category.objects.all()
    
    email = request.session.get('faculty_email', '') or getattr(request.user, 'email', '')
    if request.user.is_authenticated and request.user.username:
        faculty_display_name = request.user.username
    elif email:
        faculty_display_name = email.split('@')[0]
    else:
        faculty_display_name = 'User'

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
    from deliveries.utils import serialize_delivery
    if request.user.is_authenticated:
        ongoing_deliveries = DeliveryRequest.objects.filter(
            order__customer=request.user).order_by('-requested_at')[:5]
    else:
        ongoing_deliveries = []

    ongoing_data = [serialize_delivery(d) for d in ongoing_deliveries]

    context = {
        'menu_items': menu_items,
        'categories': categories,
        'menu_data_json': json.dumps(formatted_menu),
        'faculty_display_name': faculty_display_name,
        'ongoing_deliveries_json': json.dumps(ongoing_data),
        'user_points': float(request.user.loyalty_points) if request.user.is_authenticated else 0.0,
    }
    return render(request, 'accounts/dashboard.html', context)


# Separate Staff Login View
@ensure_csrf_cookie
@csrf_protect
def staff_login_view(request):
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
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None and (getattr(user, 'role', '') in ['DELIVERY', 'RIDER'] or user.is_staff):
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


@ensure_csrf_cookie
def send_signup_otp(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip().lower()
            otp_code = f"{random.randint(100000, 999999)}"
            
            if not email.endswith('@psu.palawan.edu.ph'):
                return JsonResponse({'success': False, 'error': 'Invalid institutional email. Must end with @psu.palawan.edu.ph'}, status=400)
            local_part = email.split('@')[0] if '@' in email else ''
            if local_part.isdigit() or not any(c.isalpha() for c in local_part):
                return JsonResponse({'success': False, 'error': 'Institutional email cannot consist solely of numbers. It must contain letters before @psu.palawan.edu.ph.'}, status=400)
            
            rate_result = _otp_rate_allowed(request.session, 'signup')
            if rate_result:
                return JsonResponse({'success': False, 'error': 'Please wait a minute before requesting another code.' if rate_result == 'cooldown' else 'Too many OTP requests. Please wait 10 minutes.'}, status=429)

            request.session['signup_otp'] = otp_code
            request.session['signup_email'] = email
            request.session['otp_verified'] = False
            request.session['signup_otp_created_at'] = int(time.time())
            request.session['signup_otp_attempts'] = 0

            email_sent = True
            try:
                send_mail(
                    subject='Canteen Express - Your OTP Verification Code',
                    message=(
                        f'Hello,\n\n'
                        f'Your Canteen Express verification OTP code is: {otp_code}\n\n'
                        f'This code expires in 10 minutes. If you did not request this, please ignore this email.\n\n'
                        f'- Canteen Express Team'
                    ),
                    from_email='Canteen Express <canteenexpress26@gmail.com>',
                    recipient_list=[email],
                    fail_silently=False,
                )
            except Exception:
                email_sent = False

            return JsonResponse({
                'success': True,
                'otp_code': otp_code,
                'email_sent': email_sent,
                'message': 'OTP sent to your institutional email.' if email_sent else 'Email delivery failed. Use the on-screen OTP instead.'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)


@ensure_csrf_cookie
def verify_signup_otp(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            entered_otp = data.get('otp', '').strip()
            session_otp = request.session.get('signup_otp')
            created_at = request.session.get('signup_otp_created_at', 0)
            attempts = request.session.get('signup_otp_attempts', 0)

            if not session_otp or not created_at or (int(time.time()) - created_at) > 600:
                return JsonResponse({'success': False, 'error': 'OTP expired. Please request a new code.'}, status=400)
            if attempts >= 5:
                return JsonResponse({'success': False, 'error': 'Too many incorrect attempts. Please request a new code.'}, status=400)

            if entered_otp == session_otp:
                request.session['otp_verified'] = True
                request.session['signup_otp'] = None
                return JsonResponse({'success': True})
            request.session['signup_otp_attempts'] = attempts + 1
            return JsonResponse({'success': False, 'error': 'Invalid or expired OTP code.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)


@ensure_csrf_cookie
def send_password_reset_otp(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip().lower()
            otp_code = f"{random.randint(100000, 999999)}"
            
            if not email.endswith('@psu.palawan.edu.ph'):
                return JsonResponse({'success': False, 'error': 'Invalid institutional email. Must end with @psu.palawan.edu.ph'}, status=400)
            
            if not User.objects.filter(email=email).exists():
                return JsonResponse({'success': False, 'error': 'No account found with this institutional email.'}, status=400)
            
            rate_result = _otp_rate_allowed(request.session, 'reset')
            if rate_result:
                return JsonResponse({'success': False, 'error': 'Please wait a minute before requesting another code.' if rate_result == 'cooldown' else 'Too many OTP requests. Please wait 10 minutes.'}, status=429)

            request.session['reset_otp'] = otp_code
            request.session['reset_email'] = email
            request.session['reset_otp_verified'] = False
            request.session['reset_otp_created_at'] = int(time.time())
            request.session['reset_otp_attempts'] = 0

            email_sent = True
            try:
                send_mail(
                    subject='Canteen Express - Your Password Reset OTP',
                    message=(
                        f'Hello,\n\n'
                        f'Your Canteen Express password reset OTP code is: {otp_code}\n\n'
                        f'This code expires in 10 minutes. If you did not request this, please ignore this email.\n\n'
                        f'- Canteen Express Team'
                    ),
                    from_email='Canteen Express <canteenexpress26@gmail.com>',
                    recipient_list=[email],
                    fail_silently=False,
                )
            except Exception:
                email_sent = False

            return JsonResponse({
                'success': True,
                'otp_code': otp_code,
                'email_sent': email_sent,
                'message': 'OTP sent to your institutional email.' if email_sent else 'Email delivery failed. Use the on-screen OTP instead.'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)


@ensure_csrf_cookie
def verify_and_reset_password(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip().lower()
            entered_otp = data.get('otp', '').strip()
            new_password = data.get('new_password')
            
            session_otp = request.session.get('reset_otp')
            session_email = request.session.get('reset_email')
            created_at = request.session.get('reset_otp_created_at', 0)
            attempts = request.session.get('reset_otp_attempts', 0)

            if not session_email or session_email != email or not session_otp or not created_at:
                return JsonResponse({'success': False, 'error': 'Invalid or expired OTP code.'}, status=400)
            if (int(time.time()) - created_at) > 600:
                return JsonResponse({'success': False, 'error': 'OTP expired. Please request a new code.'}, status=400)
            if attempts >= 5:
                return JsonResponse({'success': False, 'error': 'Too many incorrect attempts. Please request a new code.'}, status=400)
            if entered_otp != session_otp:
                request.session['reset_otp_attempts'] = attempts + 1
                return JsonResponse({'success': False, 'error': 'Invalid or expired OTP code.'}, status=400)
            
            if not is_strong_password(new_password):
                return JsonResponse({'success': False, 'error': 'Password must be at least 6 characters.'}, status=400)
            
            user = User.objects.filter(email=email).first()
            if not user:
                return JsonResponse({'success': False, 'error': 'User not found.'}, status=400)
            
            user.set_password(new_password)
            user.save()
            
            request.session.pop('reset_otp', None)
            request.session.pop('reset_email', None)
            request.session.pop('reset_otp_verified', None)
            
            return JsonResponse({'success': True, 'message': 'Password successfully reset.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)
