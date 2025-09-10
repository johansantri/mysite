import datetime
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache

class ActiveUserMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            now = datetime.datetime.now()
            cache.set(f'seen_{request.user.id}', now, timeout=300)  # 5 menit
