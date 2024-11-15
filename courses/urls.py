from django.urls import path

from . import views

app_name = 'courses'

urlpatterns = [
    path("course/", views.courseView, name= "course_view"),
    path("partner/", views.partnerView, name= "partner_view"),
    path("course-add/", views.course_create_view, name= "course_create_view"),
    path("partner-add/", views.partner_create_view, name= "partner_create_view"),
    
   
   
]