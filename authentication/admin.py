from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from import_export.admin import ImportExportModelAdmin
from .models import CustomUser, Universiti

class UniversitiAdmin(ImportExportModelAdmin):
    list_display = ('name', 'slug', 'location')
    search_fields = ('name', 'location')
    list_per_page = 10
admin.site.register(Universiti, UniversitiAdmin)

class LightweightUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'is_active')
    list_select_related = ('university',)
    search_fields = ('username', 'email')
    ordering = ('email',)
    list_per_page = 10

admin.site.register(CustomUser, LightweightUserAdmin)
