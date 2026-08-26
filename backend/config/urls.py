# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='kiosk/', permanent=False)),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('kiosk/', include('customer_portal.urls')),
    path('menu/', include('canteen_menu.urls')),
    
    # Delivery Staff App Route
    path('delivery/', include('deliveries.urls')),
]