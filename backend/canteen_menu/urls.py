from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = 'canteen_menu'

urlpatterns = [
    # Staff CRUD Routes
    path('', views.staff_menu_list, name='staff_menu_list'),
    path('add/', views.staff_menu_create, name='staff_menu_create'),
    path('<int:pk>/edit/', views.staff_menu_update, name='staff_menu_update'),
    path('<int:pk>/delete/', views.staff_menu_delete, name='staff_menu_delete'),
    path('item/<int:pk>/toggle/', views.staff_menu_toggle_availability, name='staff_menu_toggle'),
    path('categories/add/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_update, name='category_update'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    path('counter-board/', views.counter_board, name='counter_board'),
    path('dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('api/process-barcode/', views.process_barcode_api, name='process_barcode_api'),
    path('counter/pos/', views.counter_pos_view, name='counter_pos'),
    path('staff/dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('item/<int:pk>/toggle-ajax/', views.staff_menu_toggle_ajax, name='staff_menu_toggle_ajax'),
    path('item/edit-ajax/', views.staff_menu_edit_ajax, name='staff_menu_edit_ajax'),
    path('delivery-staff/create/', views.create_delivery_staff_view, name='create_delivery_staff'),
    path('delivery-staff/<int:pk>/status/', views.update_delivery_staff_status_view, name='update_delivery_staff_status'),
    path('users/<int:pk>/status/', views.update_user_status_view, name='update_user_status'),
    path('reports/export/<str:format_type>/', views.export_report_view, name='export_report'),
]