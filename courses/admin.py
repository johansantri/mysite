from django.contrib import admin
from . import models 
from .models import Partner

admin.site.register(models.Course)
admin.site.register(models.Section)
class PartnerAdmin(admin.ModelAdmin):
    autocomplete_fields = ['user','author']  # This will apply autocomplete to the 'user' ForeignKey field
    search_fields = ['name', 'abbreviation', 'user__username']
admin.site.register(Partner, PartnerAdmin)
admin.site.register(models.Category)
# Register your models here.
