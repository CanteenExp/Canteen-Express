from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect  # <--- Added this import

urlpatterns = [
    # 1. Automatically redirect root URL (127.0.0.1:8000/) to /kiosk/
    path('', lambda request: redirect('kiosk/')),

    # 2. Your existing app paths
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('kiosk/', include('customer_portal.urls')),
]