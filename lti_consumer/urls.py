from django.urls import path
from . import views
from lti_consumer.jwks_views import platform_jwks

app_name = "lti_consumer"

urlpatterns = [
    # LTI 1.3 endpoints
    path("lti13/launch/<int:link_id>/", views.lti_launch_request, name="lti13_launch"),
    path("lti13/launch/response/", views.lti_launch_response, name="lti13_launch_response"),
    path("lti13/.well-known/jwks.json", platform_jwks),
]
