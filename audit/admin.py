from django.contrib import admin
from .models import AuditLog
from authentication.models import CustomUser
from django.db.models import Count

class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'content_type', 'timestamp', 'object_id','device_type')
    list_filter = ('action', 'user', 'timestamp')
    search_fields = ('content_type__model', 'user__username')

    # Optimasi pencarian dengan memasukkan indeks pada user dan timestamp
    list_select_related = ('user', 'content_type')

    # Batasi tampilan data untuk menghindari banyak data yang diload sekaligus
    list_per_page = 50  # Menampilkan 50 per halaman untuk mengurangi beban

    # Agregasi untuk melihat seberapa banyak tindakan yang dilakukan oleh user tertentu (contoh)
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['user_activity'] = AuditLog.objects.values('user').annotate(num_actions=Count('user'))
        return super().changelist_view(request, extra_context=extra_context)

admin.site.register(AuditLog, AuditLogAdmin)
