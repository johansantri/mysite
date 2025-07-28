# authentication/urls.py
from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    path('', views.home, name='home'),
   
    path('about/',views.about, name='about'),
    path('search/', views.search, name='search'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('activate/<uidb64>/<token>/', views.activate_account, name='activate'),

    # Custom Password Reset Views
   
    path('password_reset/', views.custom_password_reset, name='password_reset'),
    path('password_reset/done/', views.custom_password_reset_done, name='password_reset_done'),
    path('reset/<uidb64>/<token>/', views.custom_password_reset_confirm, name='password_reset_confirm'),  # Ensure this is defined
    path('reset/done/', views.custom_password_reset_complete, name='password_reset_complete'),
    

    #data
    path('popular_courses/', views.popular_courses, name='popular_courses'),
    #path('profile/(?P<username>\w+)/$', views.pro, name='profile'),
    path('profile/<slug:username>/',views.pro, name='profile'), 
    path('edit-profile/<int:pk>/',views.edit_profile, name='edit-profile'), 
    path('edit-photo/<int:pk>/',views.edit_photo, name='edit-photo'), 
    
    #admin,partner, instructur
    path('dasbord/',views.dasbord, name='dasbord'),
    #student
    path('dashbord/',views.dashbord, name='dashbord'),

    path('all-user/',views.all_user,name='all-user'),
    path('user/<int:user_id>/', views.user_detail, name='user_detail'),  # Add this line
    path('course_list/', views.course_list, name='course_list'),
    path('microcredential/',views.microcredential_list, name='microcredential'),
    path('mycourse/',views.mycourse, name='mycourse'),
    path('reply-comment/<int:comment_id>/', views.reply_comment, name='reply_comment'),
    
]