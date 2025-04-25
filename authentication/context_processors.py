from courses.models import SearchHistory

from django.core.cache import cache

def search_history_context(request):
    search_history = []

    if request.user.is_authenticated:
        search_history = SearchHistory.objects.filter(user=request.user).order_by('-search_date')[:10]
    else:
        cache_key = f"search_history_anonymous_{request.session.session_key or 'default'}"
        search_history = cache.get(cache_key, [])

    return {
        'search_history': search_history
    }