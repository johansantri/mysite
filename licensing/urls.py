# licensing/urls.py
from django.urls import path
from . import views

app_name = 'licensing'

urlpatterns = [
    path('licens-dashboard/', views.licens_dashboard, name='licens_dashboard'),
    
    
   
   
]