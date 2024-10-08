from django.urls import path

from . import views

app_name = 'partner'

urlpatterns = [
    path("list/", views.partnerView, name= "partner_view"),
    path("partner-add/", views.partnerAdd, name= "partner_add"),
    path("partner-edit/<str:pk>", views.partnerEdit, name= "partner_edit"),

   
]