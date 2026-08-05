# canteen_menu/urls.py
from django.urls import path
from . import views

app_name = 'canteen_menu'

urlpatterns = [
    path('', views.menu_list_view, name='menu_list'),
]