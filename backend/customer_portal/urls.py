from django.urls import path
from . import views

urlpatterns = [
    # Changed from 'kiosk/' to ''
    path('', views.kiosk_welcome, name='kiosk_welcome'),
    
    # Changed from 'kiosk/home/' to 'home/'
    path('home/', views.kiosk_home, name='kiosk_home'),

    path('auth/', views.kiosk_auth, name='kiosk_auth'),

    path('kiosk/menu/', views.kiosk_menu, name='kiosk_menu'),
]