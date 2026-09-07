from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.http import HttpResponse
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Health Check for UptimeRobot / Keep-Alive
    path('healthz/', lambda request: HttpResponse("OK")),

    # Redirect root URL to Accounts Landing (Role Selection)
    path('', lambda request: redirect('accounts:landing')),

    # Admin
    path('admin/', admin.site.urls),

    # Accounts
    path('accounts/', include('accounts.urls')),

    # Customer / Kiosk Portal
    path('kiosk/', include('customer_portal.urls')),

    # Kitchen / Canteen Staff
    path('kitchen/', include(('kitchen_display.urls', 'kitchen'), namespace='kitchen')),

    # Canteen Menu
    path('canteen/', include(('canteen_menu.urls', 'canteen_menu'), namespace='canteen_menu')),

    # Deliveries
    path('deliveries/', include(('deliveries.urls', 'deliveries'), namespace='deliveries')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
