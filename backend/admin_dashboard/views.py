from django.shortcuts import render
from accounts.decorators import role_required

@role_required(allowed_roles=['STAFF', 'ADMIN'])
def kitchen_dashboard(request):
    
    context = {
        'staff_name': request.user.first_name or request.user.username,
    }
    return render(request, 'kitchen_dashboard.html', context)