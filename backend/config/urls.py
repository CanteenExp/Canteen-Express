# backend/config/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('kiosk/', include('customer_portal.urls')),
    path('kitchen/', include('kitchen_display.urls')),
]