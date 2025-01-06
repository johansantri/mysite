from django.urls import path

from . import views

app_name = 'courses'

urlpatterns = [
    path('courses/', views.courseView, name='course_view'),
    path('instructor-add/', views.become_instructor, name='instructor_add'),
    path('instructor/', views.instructor_view, name='instructor_view'),
    path('instructor/<int:instructor_id>/check/', views.instructor_check, name='instructor_check'),
    path('instructor/<int:instructor_id>/delete/', views.delete_instructor, name='delete_instructor'),
    path('instructor/<int:id>/', views.instructor_detail, name='instructor_detail'),
    path("studio/<str:id>", views.studio, name= "studio"),
    path("partner/", views.partnerView, name= "partner_view"),
    path('search_users/', views.search_users, name='search_users'),
    path('search_partner/', views.search_partner, name='search_partner'),
    path("course-add/", views.course_create_view, name= "course_create_view"),
    path("partner-add/", views.partner_create_view, name= "partner_create_view"),
    path('create-section/', views.create_section, name='create_section'),
    path('delete-section/<int:pk>/', views.delete_section, name='delete_section'),
    path('update-section/<int:pk>/', views.update_section, name='update_section'),
    path('course-profile/<int:id>/', views.course_profile, name='course_profile'),
    path('course-team/<int:id>/', views.course_team, name='course_team'),
    path('team-member/remove/<int:member_id>/', views.remove_team_member, name='remove_team_member'),
    
    
   
   
]