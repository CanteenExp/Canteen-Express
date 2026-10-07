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

from customer_portal.views import _get_formatted_menu

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

def _send_otp_email(to_email, subject, message):
    import urllib.request
    import urllib.error
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=None,
            recipient_list=[to_email],
            fail_silently=False,
        )
        return True
    except Exception as smtp_err:
        print(f"SMTP send failed: {smtp_err}")
        
    api_key = getattr(settings, 'EMAIL_HOST_PASSWORD', '') or os.getenv('EMAIL_HOST_PASSWORD', '')
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or os.getenv('DEFAULT_FROM_EMAIL', 'Canteen Express <onboarding@resend.dev>')
    
    if api_key and (api_key.startswith('re_') or 'resend' in str(getattr(settings, 'EMAIL_HOST', '')).lower()):
        try:
            url = 'https://api.resend.com/emails'
            payload = {
                "from": from_email,
                "to": [to_email],
                "subject": subject,
                "html": f"<div style='font-family:sans-serif;font-size:16px;line-height:1.5;color:#333;'><p>{message.replace(chr(10), '<br>')}</p></div>"
            }
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status in (200, 201):
                    print(f"Resend HTTP API send OK -> {to_email}")
                    return True
        except urllib.error.HTTPError as he:
            err_body = he.read().decode('utf-8') if he.fp else ''
            print(f"Resend HTTP API HTTPError {he.code}: {err_body}")
        except Exception as resend_err:
            print(f"Resend HTTP API fallback failed: {resend_err}")
            
    return False

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
    lock_until = cache.get(f'login_lock_until_{key}_{ip}')
    if lock_until:
        remaining = int(lock_until - time.time())
        if remaining > 0:
            return remaining
        else:
            cache.delete(f'login_lock_until_{key}_{ip}')
            cache.delete(f'login_fail_{key}_{ip}')
    return 0


def _login_attempt_failed(request, key):
    ip = _client_ip(request)
    counter = cache.get(f'login_fail_{key}_{ip}', 0) + 1
    cache.set(f'login_fail_{key}_{ip}', counter, timeout=900)
    if counter >= 5:
        cache.set(f'login_lock_until_{key}_{ip}', time.time() + 60, timeout=900)


def _login_clear(request, key):
    ip = _client_ip(request)
    cache.delete(f'login_fail_{key}_{ip}')
    cache.delete(f'login_lock_until_{key}_{ip}')

def landing_view(request):
    # Already logged in? Skip the role-picker and go straight to the role dashboard
    # instead of bouncing the user around a static landing page.
    if request.user.is_authenticated:
        return redirect(role_portal(request.user))
    return render(request, 'accounts/landing.html')


def access_denied_view(request):
    """Shown when a logged-in user opens a page meant for a different role."""
    user_role = getattr(request.user, 'role', '')
    referer = request.META.get('HTTP_REFERER', '')
    
    login_url = 'accounts:landing'

    if 'faculty' in referer or 'dashboard' in referer or user_role == 'FACULTY':
        login_url = 'accounts:faculty_auth'
    elif 'staff' in referer or 'canteen' in referer or user_role in ('STAFF', 'ADMIN') or request.user.is_staff:
        login_url = 'accounts:staff_login'
    elif 'delivery' in referer or 'rider' in referer or user_role in ('DELIVERY', 'RIDER'):
        login_url = 'accounts:delivery_login'
    elif user_role == 'STUDENT':
        login_url = 'accounts:landing'
    else:
        if user_role == 'FACULTY':
            login_url = 'accounts:faculty_auth'
        elif user_role in ('STAFF', 'ADMIN') or request.user.is_staff:
            login_url = 'accounts:staff_login'
        elif user_role in ('DELIVERY', 'RIDER'):
            login_url = 'accounts:delivery_login'

    return render(request, 'accounts/access_denied.html', {'login_url': login_url})

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
            
            local_part = email.split('@')[0] if '@' in email else ''
            if not (_is_valid_email(email) and email.endswith('@psu.palawan.edu.ph')):
                error = "Please enter a valid @psu.palawan.edu.ph email address."
                mode = 'signup'
            elif not any(c.isalpha() for c in local_part):
                error = "Email username before @psu.palawan.edu.ph must contain letters (cannot be numbers only)."
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
                        elif not user_obj.is_active or user_obj.account_status in ('banned', 'restricted', 'held', 'penalized'):
                            status_lbl = user_obj.account_status.upper() if user_obj.account_status else 'BANNED/RESTRICTED'
                            reason_txt = f"\nReason: {user_obj.status_reason}" if user_obj.status_reason else ""
                            error = f"⚠️ Account Access Denied!\nYour account has been {status_lbl}.{reason_txt}\nPlease contact canteen administration."
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
    if request.user.is_authenticated and (request.user.get_full_name() or request.user.first_name):
        faculty_display_name = request.user.get_full_name() or request.user.first_name
    elif request.user.is_authenticated and request.user.username:
        faculty_display_name = request.user.username
    elif email:
        faculty_display_name = email.split('@')[0]
    else:
        faculty_display_name = 'User'

    # Single source of truth for the menu payload: the kiosk's helper already
    # applies the canonical filter (is_available), ordering (newest first) and
    # field set. Reusing it keeps the faculty cart, its beverage-pairing dropdown
    # and every other menu surface identical to the kiosk instead of relying on a
    # hand-copied duplicate that silently drifts (that is what made the faculty
    # beverage list come out in a different, arbitrary order).
    formatted_menu = _get_formatted_menu()

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
        'enforce_geofence': getattr(settings, 'ENFORCE_GEOFENCE', True),
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
            user_obj = User.objects.filter(username=username).first()
            if user_obj and (user_obj.is_staff or getattr(user_obj, 'role', '') in ['STAFF', 'ADMIN']):
                if not user_obj.is_active or user_obj.account_status in ('banned', 'restricted', 'held', 'penalized'):
                    status_lbl = user_obj.account_status.upper() if user_obj.account_status else 'BANNED/INACTIVE'
                    reason_txt = f"\nReason: {user_obj.status_reason}" if user_obj.status_reason else ""
                    error = f"⚠️ Account Access Denied!\nYour account has been {status_lbl}.{reason_txt}\nPlease contact canteen administration."
                else:
                    user = authenticate(request, username=username, password=password)
                    if user is not None:
                        logout(request)
                        login(request, user)
                        request.session.cycle_key()
                        _login_clear(request, 'staff')
                        return redirect('canteen_menu:staff_dashboard')
                    else:
                        _login_attempt_failed(request, 'staff')
                        error = "Invalid canteen staff credentials."
            else:
                _login_attempt_failed(request, 'staff')
                error = "Invalid canteen staff credentials."
    return render(request, 'accounts/staff_login.html', {'error': error})


# Separate Delivery Personnel Login View
@ensure_csrf_cookie
@csrf_protect
def delivery_login_view(request):
    error = None
    lock_secs = _login_locked(request, 'rider')
    if request.method == 'POST':
        if lock_secs > 0:
            error = f"Too many failed attempts. Please try again in {lock_secs} seconds."
        else:
            username = request.POST.get('username')
            password = request.POST.get('password')
            user_obj = User.objects.filter(username=username).first()
            if user_obj and (getattr(user_obj, 'role', '') in ['DELIVERY', 'RIDER'] or user_obj.is_staff):
                if not user_obj.is_active or user_obj.account_status in ('banned', 'restricted', 'held', 'penalized'):
                    status_lbl = user_obj.account_status.upper() if user_obj.account_status else 'BANNED/INACTIVE'
                    reason_txt = f"\nReason: {user_obj.status_reason}" if user_obj.status_reason else ""
                    error = f"⚠️ Account Access Denied!\nYour account has been {status_lbl}.{reason_txt}\nPlease contact canteen administration."
                else:
                    user = authenticate(request, username=username, password=password)
                    if user is not None:
                        logout(request)
                        login(request, user)
                        request.session.cycle_key()
                        _login_clear(request, 'rider')
                        return redirect('deliveries:dashboard')
                    else:
                        _login_attempt_failed(request, 'rider')
                        lock_secs = _login_locked(request, 'rider')
                        error = f"Invalid delivery personnel credentials. {f'Locked for {lock_secs}s.' if lock_secs > 0 else ''}"
            else:
                _login_attempt_failed(request, 'rider')
                lock_secs = _login_locked(request, 'rider')
                error = f"Invalid delivery personnel credentials. {f'Locked for {lock_secs}s.' if lock_secs > 0 else ''}"
    return render(request, 'accounts/delivery_login.html', {'error': error, 'lock_seconds': lock_secs})


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
            local_part = email.split('@')[0] if '@' in email else ''
            otp_code = f"{random.randint(100000, 999999)}"
            
            if not (_is_valid_email(email) and email.endswith('@psu.palawan.edu.ph')):
                return JsonResponse({'success': False, 'error': 'Please enter a valid @psu.palawan.edu.ph email address.'}, status=400)
            if not any(c.isalpha() for c in local_part):
                return JsonResponse({'success': False, 'error': 'Email username before @psu.palawan.edu.ph must contain letters (cannot be numbers only).'}, status=400)

            rate_result = _otp_rate_allowed(request.session, 'signup')
            ip_rate_result = _ip_otp_rate_allowed(request, 'signup')
            if rate_result or ip_rate_result:
                return JsonResponse({'success': False, 'error': 'Please wait a minute before requesting another code.' if (rate_result or ip_rate_result) == 'cooldown' else 'Too many OTP requests. Please wait 10 minutes.'}, status=429)

            request.session['signup_otp'] = _otp_hash(otp_code)
            request.session['signup_email'] = email
            request.session['otp_verified'] = False
            request.session['signup_otp_created_at'] = int(time.time())
            request.session['signup_otp_attempts'] = 0

            email_sent = _send_otp_email(
                to_email=email,
                subject='Canteen Express - Your OTP Verification Code',
                message=(
                    f'Hello,\n\n'
                    f'Your Canteen Express verification OTP code is: {otp_code}\n\n'
                    f'This code expires in 10 minutes. If you did not request this, please ignore this email.\n\n'
                    f'- Canteen Express Team'
                )
            )

            if email_sent:
                return JsonResponse({
                    'success': True,
                    'email_sent': True,
                    'message': 'OTP sent to your email.'
                })
            # The code never left the server, so discard the half-open signup
            # state; otherwise the verification endpoint sees a plausible
            # session and rejects the user with an opaque 400.
            for _key in ('signup_otp', 'signup_email', 'signup_otp_created_at', 'signup_otp_attempts'):
                request.session.pop(_key, None)
            
            return JsonResponse({
                'success': True,
                'email_sent': False,
                'message': 'Email delivery failed. Use the on-screen OTP instead.',
                'otp_code': otp_code,
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

            email_sent = _send_otp_email(
                to_email=email,
                subject='Canteen Express - Your Password Reset OTP',
                message=(
                    f'Hello,\n\n'
                    f'Your Canteen Express password reset OTP code is: {otp_code}\n\n'
                    f'This code expires in 10 minutes. If you did not request this, please ignore this email.\n\n'
                    f'- Canteen Express Team'
                )
            )

            if email_sent:
                return JsonResponse({
                    'success': True,
                    'email_sent': True,
                    'message': 'OTP sent to your email.'
                })
            # The code never left the server, so a live reset must NOT stay
            # armed in the session: it would otherwise look valid to the
            # confirm endpoint and surface to the user as a confusing HTTP 400
            # instead of the real cause. Clear every trace of the attempt.
            request.session.pop('reset_otp', None)
            request.session.pop('reset_email', None)
            request.session.pop('reset_otp_verified', None)
            request.session.pop('reset_otp_created_at', None)
            request.session.pop('reset_otp_attempts', None)
            
            return JsonResponse({
                'success': True,
                'email_sent': False,
                'message': 'Email delivery failed. Use the on-screen OTP instead.',
                'otp_code': otp_code,
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


@ensure_csrf_cookie
@csrf_protect
def change_password_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=401)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            current_password = data.get('current_password', '')
            new_password = data.get('new_password', '')
            confirm_password = data.get('confirm_password', '')

            if not new_password or not confirm_password:
                return JsonResponse({'success': False, 'error': 'New password and confirmation are required.'}, status=400)
            
            if new_password != confirm_password:
                return JsonResponse({'success': False, 'error': 'New passwords do not match.'}, status=400)

            user = request.user
            if user.has_usable_password() and current_password:
                if not user.check_password(current_password):
                    return JsonResponse({'success': False, 'error': 'Incorrect current password.'}, status=400)
            elif user.has_usable_password() and not current_password:
                return JsonResponse({'success': False, 'error': 'Current password is required.'}, status=400)

            try:
                validate_password(new_password, user=user)
            except ValidationError as e:
                return JsonResponse({'success': False, 'error': ' '.join(e.messages)}, status=400)

            user.set_password(new_password)
            user.save()

            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, user)

            return JsonResponse({'success': True, 'message': 'Password successfully updated.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

