from django.shortcuts import render
from accounts.decorators import role_required

@role_required(allowed_roles=['STAFF'])
def kitchen_dashboard(request):
    return render(request, 'kitchen_dashboard.html')