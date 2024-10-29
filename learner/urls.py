from django.urls import path

from . import views

app_name = 'learner'

urlpatterns = [
    path("learner/", views.learnerView, name= "learner_view"),
    path("learner-add/", views.learnerAdd, name= "learner_add"),
    path("learner-edit/<str:pk>", views.learnerEdit, name= "learner_edit"),

   
]