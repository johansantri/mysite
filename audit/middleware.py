import threading
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)

# Thread-local storage untuk menyimpan user dan request
_thread_locals = threading.local()

def get_current_user():
    """Get the current user from thread-local storage. Returns None if no user is set."""
    return getattr(_thread_locals, 'user', None)

def get_current_request():
    """Get the current request from thread-local storage. Returns None if no request is set."""
    return getattr(_thread_locals, 'request', None)


class CurrentUserMiddleware(MiddlewareMixin):
    """Middleware to store the current authenticated user and request in thread-local storage."""
    def process_request(self, request):
        """Store the user and request in thread-local storage if user is authenticated."""
        user = getattr(request, 'user', None)
        # Hanya simpan user jika terautentikasi
        if user and user.is_authenticated:
            _thread_locals.user = user
        else:
            _thread_locals.user = None
        _thread_locals.request = request

    def process_response(self, request, response):
        """Clean up thread-local storage after the request is processed."""
        self._clear_thread_locals()
        return response

    def process_exception(self, request, exception):
        """Clean up thread-local storage if an exception occurs."""
        self._clear_thread_locals()

    def _clear_thread_locals(self):
        """Helper method to clear thread-local storage."""
        try:
            del _thread_locals.user
            del _thread_locals.request
        except AttributeError:
            pass

class AuditLogMiddleware(MiddlewareMixin):
    """Middleware to attach audit log information (IP address, user agent) to the request."""
    def process_request(self, request):
        """Attach audit log information to the request object."""
        try:
            ip_address = self._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            request.audit_log_info = {
                'ip_address': ip_address,
                'user_agent': user_agent or None,
            }
        except Exception as e:
            logger.error(f"Error in AuditLogMiddleware: {str(e)}")
            request.audit_log_info = {
                'ip_address': None,
                'user_agent': None,
            }

    def _get_client_ip(self, request):
        """Get the client IP address, accounting for proxies."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Validasi sederhana untuk IP address
        if not ip or ip.lower() == 'unknown':
            return None
        try:
            # Validasi IP menggunakan model field
            from django.core.validators import validate_ipv46_address
            validate_ipv46_address(ip)
            return ip
        except Exception:
            return None