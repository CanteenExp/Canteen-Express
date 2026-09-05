# backend/kitchen_display/urls.py
from django.urls import path
from . import views

app_name = 'kitchen_display'

urlpatterns = [
    path('dashboard/', views.staff_dashboard, name='dashboard'),
    path('kitchen-board/', views.kitchen_display, name='kitchen_board'),
    path('kitchen-live-stream/', views.kitchen_live_stream, name='kitchen_live_stream'),
    path('order/<int:order_id>/update-status/', views.update_order_status, name='update_status'),
    path('menu-management/', views.manage_menu, name='manage_menu'),
    path('menu/toggle/<int:item_id>/', views.toggle_item_availability, name='toggle_availability'),
    path('admin-control/verify/', views.admin_pin_verify, name='admin_pin_verify'),
    path('admin-control/governance/', views.admin_governance, name='admin_governance'),
    path('admin-control/exit/', views.admin_logout, name='admin_logout'),
]