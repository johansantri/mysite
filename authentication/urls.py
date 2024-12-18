from django.urls import path, include
from django.contrib.auth import views as auth_views
from authentication import views
from authentication.forms import UserLoginForm, ResetPasswordConfirmForm, ResetPasswordForm
from . import views

urlpatterns = [
    # login view from auth_views with custom login template
    path('login/', auth_views.LoginView.as_view(template_name='authentication/login.html',
                                                form_class=UserLoginForm,
                                                # True means that if user is already logged in, it will redirect to homepage
                                                redirect_authenticated_user=True), name='login',
         ),

    # logout view from auth_view
    path('logout/', views.logout_view, name='logout'),

    # path for register view
    path('register/', views.register, name='register'),

    #path for activate view
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),

    #path to reset password
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='authentication/password_reset.html',
                                                                 form_class=ResetPasswordForm), name='password_reset'),

    #path to password_reset_done
    path('password_reset_done/', auth_views.PasswordResetDoneView.as_view(template_name='authentication/password_reset_done.html'), name='password_reset_done'),

    #path to password_reset_confirm
    path('password_reset_confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='authentication/password_reset_confirm.html',
                                                                                                 form_class=ResetPasswordConfirmForm), name='password_reset_confirm'),

    #path to password reset complete
    path('password_reset_complete/', auth_views.PasswordResetCompleteView.as_view(template_name='authentication/password_reset_complete.html'), name='password_reset_complete'),


    # path for homepage where successfull login will redirect
    path('', views.home, name='home'),
    #path('profile/(?P<username>\w+)/$', views.pro, name='profile'),
    path('profile/<slug:username>/',views.pro, name='profile'), 
    path('edit-profile/<int:pk>/',views.edit_profile, name='edit-profile'), 
    path('edit-profile-save/<int:pk>/', views.edit_profile_save, name='edit-profile-save'),
    path('dasbord/',views.dasbord, name='dasbord'),
    
                       




]