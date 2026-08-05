from django.urls import path
from . import views

app_name = 'customer_portal'

urlpatterns = [
    path('kiosk/', views.kiosk_menu_view, name='kiosk_menu'),
]