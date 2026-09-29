from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles import views as staticfiles_views
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import include, path


urlpatterns = [
    # Health Check for UptimeRobot / Keep-Alive
    path('healthz/', lambda request: HttpResponse('OK')),

    # Browsers request /favicon.ico at the origin regardless of any <link rel="icon">,
    # so serve the app logo here to stop a 404 appearing in every access log and to
    # give unauthenticated visitors (e.g. the password-reset screen) a real icon.
    path(
        'favicon.ico',
        staticfiles_views.serve,
        {'path': 'customer_portal/images/canteen-express-logo.png'},
    ),

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

    # Staff Activity Log (mounted at root; the API path is /api/logs/)
    path('', include(('activity_log.urls', 'activity_log'), namespace='activity_log')),

    # Deliveries
    path('deliveries/', include(('deliveries.urls', 'deliveries'), namespace='deliveries')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
