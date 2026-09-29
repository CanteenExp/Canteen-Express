from django.urls import path

from . import views

app_name = 'activity_log'

urlpatterns = [
    path('api/logs/', views.activity_log_api, name='activity_log_api'),
]
