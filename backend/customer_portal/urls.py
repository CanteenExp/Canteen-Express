# customer_portal/urls.py
from django.urls import path
from . import views

app_name = 'customer_portal'

urlpatterns = [
    path('', views.kiosk_welcome, name='kiosk_welcome'),
    path('menu/', views.kiosk_menu, name='kiosk_menu'),
    path('api/menu/', views.get_kiosk_menu_api, name='get_kiosk_menu_api'),
    path('api/checkout/', views.process_checkout, name='process_checkout'),
]