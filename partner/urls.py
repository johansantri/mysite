# instructor/urls.py
from django.urls import path
from . import views

app_name = 'partner'

urlpatterns = [
    path('partner/update/<int:partner_id>/<slug:universiti_slug>/', views.partner_update_view, name='partner_update'),
    path("partner/enrollments/", views.partner_enrollment_view, name="partner_enrollments"),

    path('explore/', views.explore, name='explore'),
   
]