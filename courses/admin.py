from django.contrib import admin
from . import models 
from .models import Partner,Course, Instructor,TeamMember
from import_export.admin import ImportExportModelAdmin

class CourseAdmin(ImportExportModelAdmin):
    list_display = ('course_name', 'course_number', 'course_run', 'category', 'level')  # Adjust based on your fields
    search_fields = ['course_name', 'course_number']  # Optional: add search functionality

# Register the model with the admin site using the ImportExportModelAdmin
admin.site.register(Course, CourseAdmin)



admin.site.register(models.Section)
class PartnerAdmin(admin.ModelAdmin):
    autocomplete_fields = ['user','author']  # This will apply autocomplete to the 'user' ForeignKey field
    search_fields = ['name', 'abbreviation', 'user__username']
admin.site.register(Partner, PartnerAdmin)
admin.site.register(models.Category)
admin.site.register(models.Instructor)
admin.site.register(models.TeamMember)
# Register your models here.
