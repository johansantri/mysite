from django.contrib import admin
from . import models 
from .models import Submission,AskOra, PeerReview, AssessmentScore,Partner,Comment,CourseComment,AssessmentRead,Choice,AssessmentSession,QuestionAnswer,CourseStatusHistory,CourseStatus,CourseProgress,MaterialRead,CalculateAdminPrice,Universiti,GradeRange,Enrollment,PricingType,CoursePrice, Instructor, Category, Course, TeamMember, Section, Material,Question, Choice, Score, AttemptedQuestion,Assessment
from import_export.admin import ImportExportModelAdmin

class CourseAdmin(ImportExportModelAdmin):
    list_display = ('course_name', 'course_number', 'course_run', 'category', 'level')  # Adjust based on your fields
    search_fields = ['course_name', 'course_number']  # Optional: add search functionality

# Register the model with the admin site using the ImportExportModelAdmin
admin.site.register(Course, CourseAdmin)

@admin.register(CalculateAdminPrice)
class CalculateAdminPriceAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'created_at')  # Menampilkan kolom utama di list view
    search_fields = ('name',)  # Memungkinkan pencarian berdasarkan nama
    list_filter = ('created_at',)  # Filter berdasarkan tanggal dibuat
    ordering = ('-created_at',)  # Urutkan dari yang terbaru

admin.site.register(models.Section)
class PartnerAdmin(admin.ModelAdmin):
    autocomplete_fields = ['user','author']  # This will apply autocomplete to the 'user' ForeignKey field
    search_fields = ['name', 'abbreviation', 'user__username']
admin.site.register(Partner, PartnerAdmin)
admin.site.register(models.Category)
admin.site.register(models.Instructor)
admin.site.register(models.TeamMember)
admin.site.register(GradeRange)
admin.site.register(Universiti)
admin.site.register(Enrollment)
admin.site.register(PricingType)
admin.site.register(CoursePrice)
admin.site.register(CourseStatusHistory)
admin.site.register(CourseStatus)
admin.site.register(AssessmentRead)
admin.site.register(QuestionAnswer)
# Register your models here.
admin.site.register(CourseProgress)
admin.site.register(MaterialRead)
admin.site.register(Choice)
admin.site.register(AssessmentSession)
admin.site.register(Comment)
admin.site.register(AskOra)
admin.site.register(CourseComment)
# Mendaftarkan model ke admin
# Mendefinisikan tampilan model Submission di Admin
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'askora', 'score', 'submitted_at')  # Kolom yang ditampilkan dalam daftar
    list_filter = ('askora', 'score')  # Menambahkan filter berdasarkan askora dan score
    search_fields = ('user__username', 'askora__title')  # Fitur pencarian berdasarkan username atau judul askora
    ordering = ('-submitted_at',)  # Urutkan berdasarkan waktu pengiriman terbaru

    # Jika ingin menampilkan beberapa field di form saat menambahkan atau mengedit Submission
    fields = ('user', 'askora', 'answer_text', 'answer_file', 'score', 'submitted_at')
    readonly_fields = ('submitted_at',)  # Menyatakan bahwa submitted_at hanya bisa dibaca (tidak bisa diedit)

# Mendaftarkan model Submission di admin
admin.site.register(Submission, SubmissionAdmin)
admin.site.register(PeerReview)
admin.site.register(AssessmentScore)

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