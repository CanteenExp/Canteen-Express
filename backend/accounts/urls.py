# accounts/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views # Pwedeng gamitin ang built-in LoginView ng Django
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.landing_view, name='landing'),
    
    # Idagdag ito:
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    
    path('faculty/location/', views.faculty_location_view, name='faculty_location'),
    path('faculty/phone/', views.faculty_phone_view, name='faculty_phone'),
]