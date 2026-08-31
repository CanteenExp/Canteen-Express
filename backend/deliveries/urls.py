from django.urls import path
from . import views

app_name = 'deliveries'

urlpatterns = [
    path('dashboard/', views.delivery_dashboard, name='dashboard'),
    path('accept/<int:delivery_id>/', views.accept_delivery, name='accept_delivery'),
    path('complete/<int:delivery_id>/', views.complete_delivery, name='complete_delivery'),
    path('messages/<int:delivery_id>/get/', views.get_delivery_messages, name='get_messages'),
    path('messages/<int:delivery_id>/send/', views.send_delivery_message, name='send_message'),
]
