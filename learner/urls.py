# learner/urls.py
from django.urls import path
from . import views

app_name = 'learner'

urlpatterns = [
    path('learner/<str:username>/', views.learner_detail, name='learner_detail'),
    
   
   
]