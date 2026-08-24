# accounts/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.landing_view, name='landing'),
    
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('staff-login/', views.staff_login_view, name='staff_login'),
    path('delivery-login/', views.delivery_login_view, name='delivery_login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='accounts:landing'), name='logout'),
    
    path('faculty/location/', views.faculty_location_view, name='faculty_location'),
    path('faculty/auth/', views.faculty_auth_view, name='faculty_auth'),
    path('faculty/dashboard/', views.faculty_dashboard_view, name='dashboard'),
]
