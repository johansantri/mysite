# instructor/urls.py
from django.urls import path
from . import views

app_name = 'partner'

urlpatterns = [
    path('partner/update/<int:partner_id>/<slug:universiti_slug>/', views.partner_update_view, name='partner_update'),
    path("partner/enrollments/", views.partner_enrollment_view, name="partner_enrollments"),
    path('reports/course-ratings/', views.partner_course_ratings, name='partner_course_ratings'),
    
    path('course-detail/<int:course_id>/comment/reply/<int:comment_id>/', views.post_comment_reply, name='post_comment_reply'),
    path('course-comments/', views.partner_course_comments, name='partner_course_comments'),
    path('explore/', views.explore, name='explore'),
    path('analytics/', views.partner_analytics_view, name='partner_analytics'),
    path('analytics/heatmap/', views.heatmap_view, name='heatmap'),
    path('analytics/login-trends/', views.login_trends_view, name='login_trends'),
    path('ping-session/', views.ping_session, name='ping_session'),
    path('analytics/duration/', views.learning_duration_view, name='learning_duration'),
    path("analytics/geography/", views.participant_geography_view, name="participant_geography"),
    path('analytics/device-usage/', views.device_usage_view, name='device_usage'),
    path('analytics/popular-courses/', views.popular_courses_view, name='popular_courses'),
    path('analytics/user-growth/', views.user_growth_view, name='user_growth'),
    path('analytics/course-completion/', views.course_completion_rate_view, name='course_completion_rate'),
    path('analytics/retention/', views.retention_rate_view, name='retention_rate'),
    path('analytics/top-courses-rating/', views.top_courses_by_rating_view, name='top_courses_by_rating'),
    path('analytics/enrollment-growth/', views.course_enrollment_growth_view, name='course_enrollment_growth'),
    path('analytics/course-dropoff/', views.course_dropoff_rate_view, name='course_dropoff_rate'),


   
]