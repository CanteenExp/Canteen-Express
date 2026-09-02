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
    
    # Specific Role Logouts & Fallback Logout
    path('logout/', views.faculty_logout_view, name='logout'),
    path('logout/faculty/', views.faculty_logout_view, name='faculty_logout'),
    path('logout/staff/', views.staff_logout_view, name='staff_logout'),
    path('logout/delivery/', views.delivery_logout_view, name='delivery_logout'),
    
    path('faculty/location/', views.faculty_location_view, name='faculty_location'),
    path('faculty/auth/', views.faculty_auth_view, name='faculty_auth'),
    path('faculty/dashboard/', views.faculty_dashboard_view, name='dashboard'),
    path('faculty/<str:token>/dashboard/', views.faculty_dashboard_view, name='dashboard_hashed'),
    path('send-otp/', views.send_signup_otp, name='send_signup_otp'),
    path('verify-otp/', views.verify_signup_otp, name='verify_signup_otp'),
    path('send-password-reset-otp/', views.send_password_reset_otp, name='send_password_reset_otp'),
    path('reset-password-confirm/', views.verify_and_reset_password, name='reset_password_confirm'),
]
