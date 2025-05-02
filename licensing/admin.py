from django.contrib import admin
from .models import License
from django.utils.html import format_html
from django.utils import timezone

class LicenseAdmin(admin.ModelAdmin):
    # Menentukan kolom yang akan ditampilkan di daftar lisensi
    list_display = (
        'name', 
        'user', 
        'license_type', 
        'start_date', 
        'expiry_date', 
        'status', 
        'university', 
        'is_expired', 
        'is_approaching_expiry'
    )
    
    # Menambahkan filter untuk kategori lisensi, status, dan universitas
    list_filter = ('license_type', 'status', 'university')
    
    # Memungkinkan pencarian berdasarkan nama lisensi, username pengguna, email, dan universitas
    search_fields = ('name', 'user__username', 'user__email', 'university__name')
    
    # Menambahkan hierarki berdasarkan tanggal kedaluwarsa
    date_hierarchy = 'expiry_date'
    
    # Pengurutan berdasarkan tanggal kedaluwarsa
    ordering = ('-expiry_date',)
    
    # Fungsi untuk menampilkan apakah lisensi sudah kedaluwarsa
    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.boolean = True
    is_expired.short_description = 'Expired'

    # Fungsi untuk menampilkan apakah lisensi hampir kedaluwarsa
    def is_approaching_expiry(self, obj):
        return obj.is_approaching_expiry()
    is_approaching_expiry.boolean = True
    is_approaching_expiry.short_description = 'Approaching Expiry'
    
    # Custom form to highlight expired licenses in red
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and obj.is_expired():
            # Highlight expired licenses in red
            form.base_fields['status'].widget.attrs['style'] = 'background-color: #FFAAAA;'
        return form
    
    # Menambahkan tindakan kustom untuk menonaktifkan lisensi yang sudah kadaluarsa
    actions = ['deactivate_expired_licenses']

    def deactivate_expired_licenses(self, request, queryset):
        """Tindakan untuk menonaktifkan lisensi yang sudah kedaluwarsa."""
        expired_licenses = queryset.filter(expiry_date__lt=timezone.now().date(), status=True)
        expired_licenses.update(status=False)
        self.message_user(request, f'{expired_licenses.count()} expired licenses have been deactivated.')

    deactivate_expired_licenses.short_description = 'Deactivate expired licenses'

# Mendaftarkan model License dan kelas admin ke panel admin
admin.site.register(License, LicenseAdmin)
