from django.urls import path

from . import views

app_name = 'courses'

urlpatterns = [
    path('courses/', views.courseView, name='course_view'),
    path("studio/<str:id>", views.studio, name= "studio"),
    path("partner/", views.partnerView, name= "partner_view"),
    path("course-add/", views.course_create_view, name= "course_create_view"),
    path("partner-add/", views.partner_create_view, name= "partner_create_view"),
    path('create-section/', views.create_section, name='create_section'),
    path('delete-section/<int:pk>/', views.delete_section, name='delete_section'),
    path('update-section/<int:pk>/', views.update_section, name='update_section'),
    
    
   
   
]