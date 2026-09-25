from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.http import JsonResponse
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.conf import settings
import random
import json
import os
import re
import time
import hashlib
import hmac

User = get_user_model()

# Central role -> portal map so every login/redirect/access-denied path agrees
# on where each role belongs. No more surprise cross-portal bounces.
def role_portal(user):
    role = getattr(user, 'role', '') or ''
    if user.is_superuser or user.is_staff or role in ('STAFF', 'ADMIN'):
        return 'canteen_menu:staff_dashboard'
    if role in ('DELIVERY', 'RIDER'):
        return 'deliveries:dashboard'
    if role == 'FACULTY':
        return 'accounts:dashboard'
    return 'customer_portal:kiosk_menu'

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

def _is_valid_email(email):
    return bool(email and _EMAIL_RE.match(email))

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

def _otp_hash(code):
    return hashlib.sha256(str(code).encode('utf-8')).hexdigest()

def _otp_verify(entered, stored_hash):
    return bool(stored_hash) and hmac.compare_digest(_otp_hash(entered), stored_hash)

def _client_ip(request):
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if fwd:
        return fwd.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')

def _ip_otp_rate_allowed(request, prefix, limit=5, window=600, cooldown=60):
    now = int(time.time())
    ip = _client_ip(request)
    base = f'otp_ip_{prefix}_{ip}'
    last = cache.get(base + '_sent_at', 0)
    count = cache.get(base + '_count', 0)
    if now - last < cooldown:
        return 'cooldown'
    if now - last >= window:
        cache.set(base + '_sent_at', now, timeout=window)
        cache.set(base + '_count', 1, timeout=window)
        return ''
    if count >= limit:
        return 'limit'
    cache.set(base + '_sent_at', now, timeout=window)
    cache.set(base + '_count', count + 1, timeout=window)
    return ''


# ===== Password-login brute-force throttle (per IP per portal) =====
# 5 wrong passwords inside 15 minutes locks that IP out of the portal for
# 15 minutes. Counters live in the cache (shared), not the session, so the
# throttle can't be reset by clearing cookies.
def _login_locked(request, key):
    ip = _client_ip(request)
    return cache.get(f'login_lock_{key}_{ip}') is not None


def _login_attempt_failed(request, key):
    ip = _client_ip(request)
    counter = cache.get(f'login_fail_{key}_{ip}', 0) + 1
    cache.set(f'login_fail_{key}_{ip}', counter, timeout=900)
    if counter >= 5:
        cache.set(f'login_lock_{key}_{ip}', True, timeout=900)


def _login_clear(request, key):
    ip = _client_ip(request)
    cache.delete(f'login_fail_{key}_{ip}')
    cache.delete(f'login_lock_{key}_{ip}')

def landing_view(request):
    # Already logged in? Skip the role-picker and go straight to the role dashboard
    # instead of bouncing the user around a static landing page.
    if request.user.is_authenticated:
        return redirect(role_portal(request.user))
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
    else:
        portal_url = role_portal(request.user) if request.user.is_authenticated else portal_url

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
            
            if not (_is_valid_email(email) and email.endswith('@psu.palawan.edu.ph')):
                error = "Please enter a valid @psu.palawan.edu.ph email address."
                mode = 'signup'
            elif password != confirm_password:
                error = "Passwords do not match."
                mode = 'signup'
            elif not request.session.get('otp_verified') or request.session.get('signup_email') != email:
                error = "Please verify your email with the OTP code first."
                mode = 'signup'
            elif User.objects.filter(email=email).exists():
                error = "An account with this email already exists. Please sign in."
                mode = 'login'
            else:
                try:
                    validate_password(
                        password,
                        user=User(username=(email.split('@')[0] or 'user'), email=email, first_name=name),
                    )
                except ValidationError as e:
                    error = ' '.join(e.messages)
                    mode = 'signup'
                    return render(request, 'accounts/faculty_auth.html', {'error': error, 'mode': mode})
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

            if _login_locked(request, 'faculty'):
                error = "Too many failed attempts. Please try again in a few minutes."
                mode = 'login'
            else:
                try:
                    user_obj = User.objects.filter(email=email).first()
                    if user_obj:
                        if not user_obj.is_email_verified:
                            error = "Please verify your email first before signing in."
                            mode = 'login'
                        else:
                            user = authenticate(request, username=user_obj.username, password=password)
                            if user is not None:
                                logout(request)
                                login(request, user)
                                request.session.cycle_key()
                                if remember_me:
                                    request.session.set_expiry(1209600)
                                else:
                                    request.session.set_expiry(0)
                                request.session['faculty_email'] = email
                                _login_clear(request, 'faculty')
                                return redirect(role_portal(user))
                            else:
                                _login_attempt_failed(request, 'faculty')
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
    menu_items = MenuItem.objects.select_related('category').filter(is_available=True)
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
    from deliveries.utils import serialize_delivery, prefetch_delivery_relations
    if request.user.is_authenticated:
        ongoing_deliveries = prefetch_delivery_relations(DeliveryRequest.objects.filter(
            order__customer=request.user).order_by('-requested_at')[:5])
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
        if _login_locked(request, 'staff'):
            error = "Too many failed attempts. Please try again in a few minutes."
        else:
            user = authenticate(request, username=username, password=password)
            if user is not None and (user.is_staff or getattr(user, 'role', '') in ['STAFF', 'ADMIN']):
                logout(request)
                login(request, user)
                request.session.cycle_key()
                _login_clear(request, 'staff')
                return redirect('canteen_menu:staff_dashboard')
            else:
                _login_attempt_failed(request, 'staff')
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
        if _login_locked(request, 'rider'):
            error = "Too many failed attempts. Please try again in a few minutes."
        else:
            user = authenticate(request, username=username, password=password)
            if user is not None and (getattr(user, 'role', '') in ['DELIVERY', 'RIDER'] or user.is_staff):
                logout(request)
                login(request, user)
                request.session.cycle_key()
                _login_clear(request, 'rider')
                return redirect('deliveries:dashboard')
            else:
                _login_attempt_failed(request, 'rider')
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
            
            if not (_is_valid_email(email) and email.endswith('@psu.palawan.edu.ph')):
                return JsonResponse({'success': False, 'error': 'Please enter a valid @psu.palawan.edu.ph email address.'}, status=400)

            rate_result = _otp_rate_allowed(request.session, 'signup')
            ip_rate_result = _ip_otp_rate_allowed(request, 'signup')
            if rate_result or ip_rate_result:
                return JsonResponse({'success': False, 'error': 'Please wait a minute before requesting another code.' if (rate_result or ip_rate_result) == 'cooldown' else 'Too many OTP requests. Please wait 10 minutes.'}, status=429)

            request.session['signup_otp'] = _otp_hash(otp_code)
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
                    from_email=None,
                    recipient_list=[email],
                    fail_silently=False,
                )
            except Exception as e:
                email_sent = False
                print(f"SMTP send failed for signup OTP: {type(e).__name__}: {e}")
                print(
                    "SMTP cfg: host="
                    + str(getattr(settings, 'EMAIL_HOST', ''))
                    + " port=" + str(getattr(settings, 'EMAIL_PORT', ''))
                    + " ssl=" + str(getattr(settings, 'EMAIL_USE_SSL', ''))
                    + " tls=" + str(getattr(settings, 'EMAIL_USE_TLS', ''))
                    + " user=" + str(getattr(settings, 'EMAIL_HOST_USER', ''))
                    + " pass_set=" + str(bool(getattr(settings, 'EMAIL_HOST_PASSWORD', '')))
                    + " from=" + str(getattr(settings, 'DEFAULT_FROM_EMAIL', ''))
                )

            if email_sent:
                return JsonResponse({
                    'success': True,
                    'email_sent': True,
                    'message': 'OTP sent to your email.'
                })
            # SMTP failed. In DEBUG the code is shown on-screen as a dev
            # convenience; in production the code is NEVER returned in the
            # response (that would leak it to the client) -- the user retries.
            if settings.DEBUG:
                return JsonResponse({
                    'success': True,
                    'email_sent': False,
                    'message': 'Email delivery failed. Use the on-screen OTP instead.',
                    'otp_code': otp_code,
                })
            return JsonResponse({
                'success': False,
                'error': 'Email delivery failed. Please try again in a moment or contact support.'
            }, status=503)
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

            if _otp_verify(entered_otp, session_otp):
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
            
            if not (_is_valid_email(email) and email.endswith('@psu.palawan.edu.ph')):
                return JsonResponse({'success': False, 'error': 'Please enter a valid @psu.palawan.edu.ph email address.'}, status=400)
            
            if not User.objects.filter(email=email).exists():
                return JsonResponse({'success': False, 'error': 'No account found with this email.'}, status=400)
            
            rate_result = _otp_rate_allowed(request.session, 'reset')
            ip_rate_result = _ip_otp_rate_allowed(request, 'reset')
            if rate_result or ip_rate_result:
                return JsonResponse({'success': False, 'error': 'Please wait a minute before requesting another code.' if (rate_result or ip_rate_result) == 'cooldown' else 'Too many OTP requests. Please wait 10 minutes.'}, status=429)

            request.session['reset_otp'] = _otp_hash(otp_code)
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
                    from_email=None,
                    recipient_list=[email],
                    fail_silently=False,
                )
                print(f"SMTP send OK for password reset OTP -> {email}")
            except Exception as e:
                email_sent = False
                print(f"SMTP send failed for password reset OTP: {type(e).__name__}: {e}")
                print(
                    "SMTP cfg: host="
                    + str(getattr(settings, 'EMAIL_HOST', ''))
                    + " port=" + str(getattr(settings, 'EMAIL_PORT', ''))
                    + " ssl=" + str(getattr(settings, 'EMAIL_USE_SSL', ''))
                    + " tls=" + str(getattr(settings, 'EMAIL_USE_TLS', ''))
                    + " user=" + str(getattr(settings, 'EMAIL_HOST_USER', ''))
                    + " pass_set=" + str(bool(getattr(settings, 'EMAIL_HOST_PASSWORD', '')))
                    + " from=" + str(getattr(settings, 'DEFAULT_FROM_EMAIL', ''))
                )

            if email_sent:
                return JsonResponse({
                    'success': True,
                    'email_sent': True,
                    'message': 'OTP sent to your email.'
                })
            # Same DEBUG-only on-screen fallback; production never returns the code.
            if settings.DEBUG:
                return JsonResponse({
                    'success': True,
                    'email_sent': False,
                    'message': 'Email delivery failed. Use the on-screen OTP instead.',
                    'otp_code': otp_code,
                })
            return JsonResponse({
                'success': False,
                'error': 'Email delivery failed. Please try again in a moment or contact support.'
            }, status=503)
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
            if not _otp_verify(entered_otp, session_otp):
                request.session['reset_otp_attempts'] = attempts + 1
                return JsonResponse({'success': False, 'error': 'Invalid or expired OTP code.'}, status=400)

            user = User.objects.filter(email=email).first()
            if not user:
                return JsonResponse({'success': False, 'error': 'User not found.'}, status=400)

            try:
                validate_password(new_password, user=user)
            except ValidationError as e:
                return JsonResponse({'success': False, 'error': ' '.join(e.messages)}, status=400)

            user.set_password(new_password)
            user.save()

            request.session.cycle_key()
            request.session.pop('reset_otp', None)
            request.session.pop('reset_email', None)
            request.session.pop('reset_otp_verified', None)
            
            return JsonResponse({'success': True, 'message': 'Password successfully reset.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)
