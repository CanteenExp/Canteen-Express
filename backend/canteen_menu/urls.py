from django.urls import path
from . import views
from django.conf import settings             # <-- DAGDAG ITO (1)
from django.conf.urls.static import static   # <-- DAGDAG ITO (2)

app_name = 'canteen_menu'

urlpatterns = [
    # Staff CRUD Routes
    path('', views.staff_menu_list, name='staff_menu_list'),
    path('add/', views.staff_menu_create, name='staff_menu_create'),
    path('<int:pk>/edit/', views.staff_menu_update, name='staff_menu_update'),
    path('<int:pk>/delete/', views.staff_menu_delete, name='staff_menu_delete'),
    path('counter-board/', views.counter_board, name='counter_board'),
    path('dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('api/process-barcode/', views.process_barcode_api, name='process_barcode_api'),
    path('counter/pos/', views.counter_pos_view, name='counter_pos'),
    path('staff/dashboard/', views.staff_dashboard, name='staff_dashboard'),
]