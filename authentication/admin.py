from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from import_export.admin import ImportExportModelAdmin
from .models import CustomUser, Universiti

class UniversitiAdmin(ImportExportModelAdmin):
    list_display = ('name', 'slug', 'location')
    search_fields = ('name', 'location')
    list_per_page = 10
admin.site.register(Universiti, UniversitiAdmin)

class CustomUserAdmin(ImportExportModelAdmin, UserAdmin):
    model = CustomUser

    list_display = (
        'username', 'email', 'first_name', 'last_name', 'is_active',
        'is_superuser', 'is_staff', 'is_member', 'university',
        'phone', 'gender', 'country', 'birth', 'photo'
    )
    list_filter = (
        'is_staff', 'is_active', 'is_member', 'university', 'gender', 'country'
    )
    search_fields = (
        'username', 'email', 'first_name', 'last_name', 'phone', 'university__name'
    )
    ordering = ('email',)
    list_per_page = 10

    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Personal info', {'fields': (
            'first_name', 'last_name', 'phone', 'gender', 'country', 'birth',
            'photo', 'address', 'university'
        )}),
        ('Permissions', {'fields': (
            'is_superuser', 'is_member', 'is_subscription', 'is_instructor',
            'is_partner', 'is_audit', 'is_learner', 'is_note', 'is_staff',
            'is_active'
        )}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Social info', {'fields': (
            'tiktok', 'instagram', 'facebook', 'youtube', 'linkedin', 'twitter'
        )}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2')
        }),
    )

    filter_horizontal = ()

admin.site.register(CustomUser, CustomUserAdmin)
