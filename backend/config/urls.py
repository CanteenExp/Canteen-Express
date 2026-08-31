from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
<<<<<<< HEAD
from django.conf import settings
from django.conf.urls.static import static
=======
from django.conf import settings             # <-- IDAGDAG ITO
from django.conf.urls.static import static   # <-- IDAGDAG ITO
>>>>>>> pilot-testing

urlpatterns = [
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

<<<<<<< HEAD
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
=======
# <-- IDAGDAG ITO SA PINAKABABA PARA LUMABAS ANG MGA PICTURES -->
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
>>>>>>> pilot-testing
