# utils/security.py

from django.core.validators import validate_slug
from django.core.exceptions import ValidationError
from django.utils.deprecation import MiddlewareMixin
from django.utils.cache import patch_vary_headers

def is_safe_slug(value):
    try:
        validate_slug(value)
        return True
    except ValidationError:
        return False

class SecurityHeadersMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        response['X-Frame-Options'] = 'DENY'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Referrer-Policy'] = 'same-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=()'
        patch_vary_headers(response, ['Origin'])
        return response
