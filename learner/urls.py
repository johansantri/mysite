# learner/urls.py
from django.urls import path
from . import views

app_name = 'learner'

urlpatterns = [
    path('learner/<str:username>/', views.learner_detail, name='learner_detail'),
    path('<str:username>/<str:slug>/', views.my_course, name='course_learn'),
    path('<str:username>/<str:slug>/<str:content_type>/<int:content_id>/', views.load_content, name='load_content'),
    path('start-assessment/<int:assessment_id>/', views.start_assessment, name='start_assessment'),
    path('submit-answer/', views.submit_answer, name='submit_answer'),
    path('add-comment/', views.add_comment, name='add_comment'),
    path('<str:username>/<str:slug>/progress/', views.get_progress, name='get_progress'),
    
   
   
]