from django.urls import path
from . import views

app_name = 'deliveries'

urlpatterns = [
    path('', views.delivery_dashboard, name='dashboard'),
    path('order/<int:order_id>/accept/', views.accept_delivery, name='accept_delivery'),
]