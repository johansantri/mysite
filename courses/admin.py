from django.contrib import admin
from . import models 
from .models import Partner,GradeRange, Instructor, Category, Course, TeamMember, Section, Material,Question, Choice, Score, AttemptedQuestion,Assessment
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
admin.site.register(GradeRange)
# Register your models here.


@admin.register(Material)

class MaterialAdmin(admin.ModelAdmin):

    list_display = ('title', 'section', 'created_at')

    list_filter = ('section',)


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4

class QuestionAdmin(admin.ModelAdmin):
    inlines = [ChoiceInline]

admin.site.register(Question, QuestionAdmin)
admin.site.register(Score)
admin.site.register(Assessment)
admin.site.register(AttemptedQuestion)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ('user', 'score', 'total_questions', 'grade', 'date')
    list_filter = ('grade', 'date')