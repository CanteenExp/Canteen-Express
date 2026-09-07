from django.urls import path
from . import views

app_name = 'deliveries'

urlpatterns = [
    path('dashboard/', views.delivery_dashboard, name='dashboard'),
    path('history/', views.delivery_history, name='history'),
    path('toggle-availability/', views.toggle_availability, name='toggle_availability'),
    path('accept/<int:delivery_id>/', views.accept_delivery, name='accept_delivery'),
    path('reject/<int:delivery_id>/', views.reject_delivery, name='reject_delivery'),
    path('cancel/<int:delivery_id>/', views.cancel_delivery, name='cancel_delivery'),
    path('complete/<int:delivery_id>/', views.complete_delivery, name='complete_delivery'),
    path('messages/<int:delivery_id>/get/', views.get_delivery_messages, name='get_messages'),
    path('messages/<int:delivery_id>/send/', views.send_delivery_message, name='send_message'),
    path('api/pool-status/', views.pool_status, name='pool_status'),
    path('api/rider-earnings-summary/', views.rider_earnings_summary, name='rider_earnings_summary'),
    path('api/rider-live-stream/', views.rider_live_stream, name='rider_live_stream'),
    path('api/pending-cards/', views.pending_cards, name='pending_cards'),
    path('api/faculty-delivery-status/', views.faculty_delivery_status, name='faculty_delivery_status'),
    path('api/faculty-delivery-stream/', views.faculty_delivery_stream, name='faculty_delivery_stream'),
    path('api/staff-dispatch-stream/', views.staff_dispatch_stream, name='staff_dispatch_stream'),
    path('api/order-detail/<int:delivery_id>/', views.get_order_detail, name='order_detail'),
    path('api/location/<int:delivery_id>/update/', views.update_location, name='update_location'),
    path('api/location/<int:delivery_id>/', views.get_tracking, name='get_tracking'),
    path('track/<int:delivery_id>/', views.track_order, name='track_order'),
]
