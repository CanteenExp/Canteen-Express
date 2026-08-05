from django.urls import path
from . import views

app_name = 'deliveries'

urlpatterns = [
    path('dashboard/', views.delivery_dashboard, name='dashboard'),
]