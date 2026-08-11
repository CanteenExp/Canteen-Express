from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    # Redirect root URL to kiosk
    path('', lambda request: redirect('/kiosk/')),

    # Admin
    path('admin/', admin.site.urls),

    # Accounts
    path('accounts/', include('accounts.urls')),

    # Customer / Kiosk (Inilagay ang namespace para gumana ang 'customer_portal:kiosk_menu')
    path('kiosk/', include(('customer_portal.urls', 'customer_portal'), namespace='customer_portal')),

    # Kitchen / Canteen Staff (Inilagay din ang namespace para sa kitchen)
    path('kitchen/', include(('kitchen_display.urls', 'kitchen'), namespace='kitchen')),
]