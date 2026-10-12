"""URLs for the manual open/close switch. Mounted under /core/."""

from django.urls import path

from . import views

app_name = 'core_app'

urlpatterns = [
    path('system/closed/', views.system_closed, name='system_closed'),
    path('system/status/', views.system_status_api, name='system_status_api'),
    path('system/toggle/', views.system_toggle_api, name='system_toggle_api'),
]
