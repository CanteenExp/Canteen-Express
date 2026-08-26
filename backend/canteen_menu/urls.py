# canteen_menu/urls.py
from django.urls import path
from . import views

app_name = 'canteen_menu'

urlpatterns = [
    # Defines the 'menu_list' route expected by your login redirect
    path('', views.menu_list, name='menu_list'),
]