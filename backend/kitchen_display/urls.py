from django.urls import path
from . import views

app_name = 'kitchen_display'

urlpatterns = [
    path('dashboard/', views.kitchen_dashboard, name='dashboard'),
]