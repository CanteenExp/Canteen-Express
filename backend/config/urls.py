from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    # Redirect root URL to kiosk
    path('', lambda request: redirect('kiosk/')),

    # Admin
    path('admin/', admin.site.urls),

    # Accounts
    path('accounts/', include('accounts.urls')),

    # Customer / Kiosk
    path('kiosk/', include('customer_portal.urls')),

    # Kitchen / Canteen Staff
    path('kitchen/', include('kitchen_display.urls')),
]