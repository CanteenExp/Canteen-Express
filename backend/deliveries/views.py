from django.shortcuts import render
from accounts.decorators import role_required

@role_required(allowed_roles=['DELIVERY'])
def delivery_dashboard(request):
    return render(request, 'delivery_dashboard.html')