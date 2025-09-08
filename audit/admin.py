from django.contrib import admin
from django.db.models import Count
from django.core.cache import cache
from datetime import datetime, timedelta

from .models import AuditLog
from authentication.models import CustomUser  # Pastikan ini import model user kamu

class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'content_type', 'timestamp', 'object_id', 'device_type')

    # Filter yang ringan (hindari user langsung)
    list_filter = ('action', 'timestamp')

    # Search hanya pada field ringan
    search_fields = ('content_type__model',)

    # Optimasi ForeignKey
    list_select_related = ('user', 'content_type')

    # Gunakan autocomplete untuk user (bukan raw_id_fields)
    autocomplete_fields = ('user',)

    # Batasi jumlah data per halaman
    list_per_page = 50

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}

        cache_key = 'auditlog:user_activity'
        stats = cache.get(cache_key)

        if not stats:
            # Ambil data 7 hari terakhir untuk mengurangi beban
            last_week = datetime.now() - timedelta(days=7)
            stats = (
                AuditLog.objects
                .filter(timestamp__gte=last_week)
                .values('user__username')
                .annotate(num_actions=Count('id'))
                .order_by('-num_actions')[:10]  # Top 10 user
            )
            cache.set(cache_key, list(stats), timeout=300)  # Cache 5 menit

        extra_context['user_activity'] = stats

        return super().changelist_view(request, extra_context=extra_context)


admin.site.register(AuditLog, AuditLogAdmin)
