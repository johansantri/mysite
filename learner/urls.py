from django.urls import path

from . import views

app_name = 'learner'

urlpatterns = [
    path("learner/", views.learnerView, name= "learner_view"),
    #path("course-add/", views.courseAdd, name= "course_add"),
    #path("course-edit/<str:pk>", views.courseEdit, name= "course_edit"),

   
]