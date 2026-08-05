# accounts/decorators.py
from django.shortcuts import redirect
from django.contrib import messages

def role_required(allowed_roles=[]):
    """
    Decorator para i-block ang access kapag hindi kasama ang role ng user sa allowed_roles.
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            # 1. Siguraduhing naka-login ang user
            if not request.user.is_authenticated:
                messages.warning(request, "Mag-login muna para ma-access ang page na ito.")
                return redirect('accounts:login')
            
            # 2. Pinapayagan ang Superuser/Admin sa lahat ng pages
            if request.user.is_superuser or request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            
            # 3. Kapag HINDI allowed ang role, harangin at i-redirect sa KANYANG tamang dashboard
            messages.error(request, "Access Denied: Bawal ka sa page na ito!")
            
            user_role = request.user.role
            if user_role in ['STUDENT', 'FACULTY']:
                return redirect('customer_portal:menu')
            elif user_role == 'STAFF':
                return redirect('kitchen_display:dashboard')
            elif user_role == 'DELIVERY':
                return redirect('deliveries:dashboard')
            elif user_role == 'ADMIN':
                return redirect('admin_dashboard:index')
            else:
                return redirect('customer_portal:menu')
                
        return _wrapped_view
    return decorator