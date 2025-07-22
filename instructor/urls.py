# instructor/urls.py
from django.urls import path
from . import views

app_name = 'instructor'

urlpatterns = [
    path('instructor/learning-report/', views.instructor_learning_report, name='instructor_learning_report'),
    path('instructor/learner-detail-report/', views.instructor_learner_detail_report, name='instructor_learner_detail_report'),
   
     # URL untuk Instructor
    path('instructor/course/<int:course_id>/submit-curation/', views.instructor_submit_curation, name='instructor_submit_curation'),
    

    # URL untuk Partner
    path('partner/course/<int:course_id>/review-curation/', views.partner_review_curation, name='partner_review_curation'),
    

    # URL untuk Superuser
    path('superuser/course/<int:course_id>/publish/', views.superuser_publish_course, name='superuser_publish_course'),
    path('studios/<str:id>/', views.studios, name='studios'),

    path('certificate/instructor/<int:course_id>/download/', views.download_instructor_certificate, name='download_instructor_certificate')
   
]