from django.contrib import admin
from .models import Payment, CartItem, Transaction


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
