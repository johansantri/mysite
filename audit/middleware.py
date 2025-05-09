# audit/middleware.py
import threading
from django.utils.deprecation import MiddlewareMixin
_user = threading.local()

class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _user.value = request.user
        return self.get_response(request)

def get_current_user():
    return getattr(_user, 'value', None)

class AuditLogMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Menyimpan IP Address pengguna
        ip_address = request.META.get('REMOTE_ADDR')
        
        # Menyimpan informasi User Agent
        user_agent = request.META.get('HTTP_USER_AGENT')

        # Menyimpan data tersebut dalam request untuk diakses di tempat lain
        request.audit_log_info = {
            'ip_address': ip_address,
            'user_agent': user_agent,
        }