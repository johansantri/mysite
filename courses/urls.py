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
    path('questions/delete/<int:idcourse>/<int:idquestion>/<int:idsection>/<int:idassessment>', views.delete_question, name='delete_question'),
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
    path('search_instructors/', views.search_instructors, name='search_instructors'),
    path('team-member/remove/<int:member_id>/', views.remove_team_member, name='remove_team_member'),
    path('draft-lms/<int:id>/', views.draft_lms, name='draft-lms'),
    path('course-detail/<int:id>/<slug:slug>/', views.course_lms_detail, name='course_lms_detail'),

    path('add-price/<int:id>/', views.add_course_price, name='add_course_price'),
    
    path('courses/re-runs/<int:id>/', views.course_reruns, name='course_reruns'),
    path('course-learn/<str:username>/<slug:slug>/', views.course_learn, name='course_learn'),
    path('submit_assessment/<int:assessment_id>/', views.submit_assessment, name='submit_assessment'),
    path('start-assessment/<int:assessment_id>/', views.start_assessment, name='start_assessment'),
    path('enroll/<int:course_id>/', views.enroll_course, name='enroll'),  # Define 'enroll' URL pattern
    path('add-comment/<int:material_id>/', views.add_comment, name='add_comment'),
    path('add-comment-course/<int:course_id>/', views.add_comment_course, name='add_comment_course'),  # Add this line
    path('course/<int:idcourse>/section/<int:idsection>/assessment/<int:idassessment>/create/', views.create_askora, name='create_askora'),
    path('edit-askora/<int:idcourse>/<int:idaskora>/<int:idsection>/<int:idassessment>/', views.edit_askora, name='edit_askora'),
    path('delete-askora/<int:idcourse>/<int:idaskora>/<int:idsection>/<int:idassessment>/', views.delete_askora, name='delete_askora'),
    #sertifikat
    path('certificate/<int:course_id>/', views.generate_certificate, name='generate_certificate'),
    path('submit-answer/<int:askora_id>/', views.submit_answer, name='submit_answer'),
    path('submit-peer-review/<int:submission_id>/', views.submit_peer_review, name='submit_peer_review'),

    path('microcredentials/', views.listmic, name='microcredential-list'),
    path('microcredentials/create/', views.addmic, name='microcredential-create'),
    path('autocomplete/', views.course_autocomplete, name='course_autocomplete'),
    path('microcredentials/<int:pk>/edit/', views.editmic, name='microcredential-update'),
    path('microcredentials/<int:pk>/delete/', views.deletemic, name='microcredential-delete'),
    path('microcredentials/<int:pk>/', views.detailmic, name='microcredential-detail'),  # Detail view
    path('microcredential/<slug:slug>/', views.microcredential_detail, name='microcredential_detail'),
    path('microcredential/<int:id>/certificate/', views.generate_microcredential_certificate, name='generate_microcredential_certificate'),
    path('microcredential/<slug:slug>/enroll/', views.enroll_microcredential, name='enroll_microcredential'),
    #detail micro lms
    path('microcredential/<int:id>/<slug:slug>', views.micro_detail, name="micro_detail")
   
   
]