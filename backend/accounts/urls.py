from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # 1. Landing & Role Selection
    path('', views.landing_view, name='landing'),
    path('role/student/', views.select_student_role_view, name='select_student'),

    # 2. Faculty Onboarding Steps
    path('faculty/location/', views.faculty_location_view, name='faculty_location'),
    path('faculty/phone/', views.faculty_phone_view, name='faculty_phone'),
    path('faculty/verify-phone/', views.faculty_verify_phone_view, name='faculty_verify_phone'),
    path('faculty/register/', views.faculty_register_view, name='faculty_register'),
    path('faculty/verify-email/', views.faculty_verify_email_view, name='faculty_verify_email'),

    # 3. Standard Login / Logout
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
]