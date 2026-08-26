# customer_portal/urls.py
from django.urls import path
from . import views

app_name = 'customer_portal'

urlpatterns = [
    # Updated from views.kiosk_menu to views.kiosk_menu_view
    path('', views.kiosk_menu_view, name='kiosk_menu'),
]