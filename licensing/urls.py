# licensing/urls.py
from django.urls import path
from . import views

app_name = 'licensing'

urlpatterns = [
    path('licens-dashboard/', views.licens_dashboard, name='licens_dashboard'),
    path('send-invitation/', views.send_invitation, name='send_invitation'),
    path('invite/<str:token>/', views.accept_invitation, name='accept_invitation'),
    
    path('accept-invitation/<uidb64>/<token>/', views.accept_invitation, name='accept_invitation'),
    path('delete_license/<int:license_id>/', views.delete_license, name='delete_license'),  # Hapus lisensi
    path('resend_invitation/<int:invitation_id>/', views.resend_invitation, name='resend_invitation'),  # Kirim ulang undangan
   
   
]