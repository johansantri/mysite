from django.urls import path
from .views import my_activity_logs


app_name = 'audit'

urlpatterns = [
    path('my-logs/', my_activity_logs, name='my_activity_logs'),
]
