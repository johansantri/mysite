from django.contrib import admin
from .models import Payment, CartItem, Transaction,Voucher, VoucherUsage


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'payment_model', 'amount', 'status', 'created_at')
    list_filter = ('payment_model', 'status', 'created_at')
    search_fields = ('user__username', 'course__course_name', 'transaction_id')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'added_at')
    search_fields = ('user__username', 'course__course_name')
    readonly_fields = ('added_at',)
    ordering = ('-added_at',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'description')
    filter_horizontal = ('courses',)
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'amount',
        'is_active',
        'start_date',
        'end_date',
        'usage_limit',
        'used_count',
        'one_time_per_user',
        'created_at',
    )
    list_filter = (
        'is_active',
        'start_date',
        'end_date',
        'one_time_per_user',
    )
    search_fields = ('code',)
    readonly_fields = ('used_count', 'created_at')

    fieldsets = (
        (None, {
            'fields': ('code', 'amount', 'is_active')
        }),
        ('Masa Berlaku', {
            'fields': ('start_date', 'end_date'),
            'description': 'Atur tanggal mulai dan berakhirnya voucher'
        }),
        ('Penggunaan', {
            'fields': ('usage_limit', 'used_count', 'one_time_per_user'),
            'description': 'Batasi jumlah penggunaan dan apakah satu kali per user'
        }),
        ('Tanggal dibuat', {
            'fields': ('created_at',),
        }),
    )

    def save_model(self, request, obj, form, change):
        # Jangan biarkan admin ubah used_count secara manual
        if change:
            obj.used_count = Voucher.objects.get(pk=obj.pk).used_count
        super().save_model(request, obj, form, change)


@admin.register(VoucherUsage)
class VoucherUsageAdmin(admin.ModelAdmin):
    list_display = ('user', 'voucher', 'used_at')
    list_filter = ('used_at',)
    search_fields = ('user__username', 'voucher__code')

    readonly_fields = ('user', 'voucher', 'used_at')

    def has_add_permission(self, request):
        # Cegah tambah manual karena otomatis tercatat saat pemakaian voucher
        return False

    def has_delete_permission(self, request, obj=None):
        # Opsional: cegah hapus voucher usage dari admin (untuk audit)
        return False
