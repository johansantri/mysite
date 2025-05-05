# licensing/urls.py
from django.urls import path
from . import views

app_name = 'licensing'

urlpatterns = [
    path('licens-dashboard/', views.licens_dashboard, name='licens_dashboard'),
    path('participant/dashboard/', views.participant_dashboard, name='participant_dashboard'),
    path('invitation/send/', views.send_invitation, name='send_invitation'),
    path('invitation/cancel/<int:invitation_id>/', views.cancel_invitation, name='cancel_invitation'),
    path('invitation/resend/<int:invitation_id>/', views.resend_invitation, name='resend_invitation'),
    path('invitation/accept/<str:uidb64>/<str:token>/', views.accept_invitation, name='accept_invitation'),
    path('create/', views.create_license, name='create_license'),
   
   
]