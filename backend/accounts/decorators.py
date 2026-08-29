# accounts/decorators.py
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse

def role_required(allowed_roles=[]):
    """
    Decorator para i-block ang access kapag hindi kasama ang role ng user sa allowed_roles.
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            is_ajax_or_api = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'json' in request.headers.get('accept', '') or '/messages/' in request.path
            is_faculty_session = 'FACULTY' in allowed_roles and request.session.get('faculty_email')

            if not request.user.is_authenticated and not is_faculty_session:
                if is_ajax_or_api:
                    return JsonResponse({'success': False, 'message': 'Authentication required'}, status=401)
                messages.warning(request, "Mag-login muna para ma-access ang page na ito.")
                if 'DELIVERY' in allowed_roles:
                    return redirect('accounts:delivery_login')
                elif 'STAFF' in allowed_roles or 'ADMIN' in allowed_roles:
                    return redirect('accounts:staff_login')
                else:
                    return redirect('accounts:login')
            
            user_role = getattr(request.user, 'role', 'FACULTY' if is_faculty_session else '')
            if request.user.is_superuser or request.user.is_staff or user_role in allowed_roles or is_faculty_session:
                return view_func(request, *args, **kwargs)
            
            if is_ajax_or_api:
                return JsonResponse({'success': False, 'message': 'Access Denied'}, status=403)

            messages.error(request, "Access Denied: Bawal ka sa page na ito!")
            
            if user_role in ['STUDENT', 'FACULTY']:
                return redirect('customer_portal:kiosk_menu')
            elif user_role == 'STAFF':
                return redirect('canteen_menu:staff_dashboard')
            elif user_role == 'DELIVERY':
                return redirect('deliveries:dashboard')
            else:
                return redirect('customer_portal:menu')
                
        return _wrapped_view
    return decorator
