from django.urls import path

from . import views

app_name = 'courses'

urlpatterns = [
    path("course/", views.courseView, name= "course_view"),
    path("course-add/", views.courseAdd, name= "course_add"),
    path("course-edit/<str:pk>", views.courseEdit, name= "course_edit"),

   
]