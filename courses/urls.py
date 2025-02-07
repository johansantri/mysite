from django.urls import path

from . import views

app_name = 'courses'

urlpatterns = [
    path('courses/', views.courseView, name='course_view'),
    path('course/<int:course_id>/enroll/', views.enroll_course, name='enroll_course'),
    path('instructor-add/', views.become_instructor, name='instructor_add'),
    path('instructor/', views.instructor_view, name='instructor_view'),
    path('instructor/<int:instructor_id>/check/', views.instructor_check, name='instructor_check'),
    path('instructor/<int:instructor_id>/delete/', views.delete_instructor, name='delete_instructor'),
    path('instructor/<int:id>/', views.instructor_detail, name='instructor_detail'),
    path('instructor-profile/<slug:username>/', views.instructor_profile, name='instructor_profile'),
    path("studio/<str:id>", views.studio, name= "studio"),
    path("partner/", views.partnerView, name= "partner_view"),
    path('partner/<int:partner_id>/', views.partner_detail, name='partner_detail'),
    path('partner/<int:partner_id>/update/', views.update_partner, name='update_partner'),
    path('org-partner/<slug:slug>/',views.org_partner, name='org_partner'),
    path('search_users/', views.search_users, name='search_users'),
    path('search_partner/', views.search_partner, name='search_partner'),
    path("course-add/", views.course_create_view, name= "course_create_view"),
    path("partner-add/", views.partner_create_view, name= "partner_create_view"),
    path('create-section/<int:idcourse>/', views.create_section, name='create_section'),
    path('add-matrial/<int:idcourse>/<int:idsection>/',views.add_matrial,name="add-matrial"),
    path('create-assessment/<int:idcourse>/<int:idsection>/', views.create_assessment, name='create-assessment'),
    path('edit-assessment/<int:idcourse>/<int:idsection>/<int:idassessment>/', views.edit_assessment, name='edit_assessment'),
    path('delete-assessment/<int:idcourse>/<int:idsection>/<int:idassessment>/', views.delete_assessment, name='delete_assessment'),
   
    
    
    path('questions/create/<int:idcourse>/<int:idsection>/<int:idassessment>/', views.create_question_view, name='create_question'),
    path('edit-matrial/<int:idcourse>/<int:idmaterial>', views.edit_matrial, name='edit_matrial'),
    path('questions/edit/<int:idcourse>/<int:idquestion>/<int:idsection>/<int:idassessment>', views.edit_question, name='edit_question'),
    path(
        'questions/view/<int:idcourse>/<int:idsection>/<int:idassessment>/',
        views.question_view,
        name='view-question',
    ),
    path('delete-matrial/<int:pk>', views.delete_matrial, name='delete_matrial'),
    path('delete-section/<int:pk>/', views.delete_section, name='delete_section'),
    path('update-section/<int:pk>/', views.update_section, name='update_section'),
    path('course-profile/<int:id>/', views.course_profile, name='course_profile'),
    path('course-grade/<int:id>/', views.course_grade, name='course_grade'),
    path("update-grade-range/<int:id>/", views.update_grade_range, name="update_grade_range"),
    path('course-team/<int:id>/', views.course_team, name='course_team'),
    path('course-instructor/<int:id>/', views.course_instructor, name='course_instructor'),
    path('team-member/remove/<int:member_id>/', views.remove_team_member, name='remove_team_member'),
    path('draft-lms/<int:id>/', views.draft_lms, name='draft-lms'),
    path('course-detail/<int:id>/<slug:slug>/', views.course_lms_detail, name='course_lms_detail'),

    path('add-price/<int:id>/', views.add_course_price, name='add_course_price'),

    path('courses/re-runs/<int:id>/', views.course_reruns, name='course_reruns'),
    
    
   
   
]