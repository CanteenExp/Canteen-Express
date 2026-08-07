from django.shortcuts import render

def kiosk_welcome(request):
    # Added 'customer_portal/' prefix
    return render(request, 'customer_portal/kiosk_welcome.html') 

def kiosk_home(request):
    # Added 'customer_portal/' prefix
    return render(request, 'customer_portal/kiosk_home.html')

def kiosk_auth(request):
    return render(request, 'customer_portal/kiosk_auth.html')