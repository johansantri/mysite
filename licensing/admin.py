from django.contrib import admin
from .models import License,Invitation
from django.utils.html import format_html
from django.utils import timezone

@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ('name', 'license_type', 'start_date', 'expiry_date', 'status', 'max_users', 'user_count')
    list_filter = ('license_type', 'status')
    search_fields = ('name',)
    
    def user_count(self, obj):
        return obj.users.count()
    user_count.short_description = 'Number of Users'

@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ('inviter', 'invitee_email', 'license', 'status', 'invitation_date', 'expiry_date')
    list_filter = ('status',)
    search_fields = ('invitee_email',)