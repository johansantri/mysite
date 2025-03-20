# instructor/urls.py
from django.urls import path
from . import views

app_name = 'instructor'

urlpatterns = [
    path('instructor/learning-report/', views.instructor_learning_report, name='instructor_learning_report'),
    path('instructor/learner-detail-report/', views.instructor_learner_detail_report, name='instructor_learner_detail_report'),
   
]