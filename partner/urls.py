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
   
]