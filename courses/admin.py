from django.contrib import admin
from . import models 
from .models import LTIPlatformConfiguration, LTIExternalTool,Submission,CourseRating,UserProfile,Hashtag,SosPost,AskOra,BlacklistedKeyword, PeerReview,MicroCredential, AssessmentScore,Partner,Comment,CourseComment,AssessmentRead,Choice,AssessmentSession,QuestionAnswer,CourseStatusHistory,CourseStatus,CourseProgress,MaterialRead,CalculateAdminPrice,Universiti,GradeRange,Enrollment,PricingType,CoursePrice, Instructor, Category, Course, TeamMember, Section, Material,Question, Choice, Score, AttemptedQuestion,Assessment
from import_export.admin import ImportExportModelAdmin



@admin.register(LTIPlatformConfiguration)
class LTIPlatformConfigurationAdmin(admin.ModelAdmin):
    list_display = ['issuer', 'client_id', 'deployment_id', 'created_at']
    readonly_fields = ['created_at']
    search_fields = ['issuer', 'client_id', 'deployment_id']
    list_filter = ['created_at']
    fields = [
        'issuer', 'client_id', 'auth_login_url', 'auth_token_url',
        'key_set_url', 'private_key', 'public_key', 'deployment_id', 'created_at'
    ]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['private_key', 'public_key', 'client_id', 'issuer']
        return self.readonly_fields

@admin.register(LTIExternalTool)
class LTIExternalToolAdmin(admin.ModelAdmin):
    list_display = ['name', 'launch_url', 'platform_config', 'has_grade', 'max_grade', 'created_at']
    readonly_fields = ['created_at']
    search_fields = ['name', 'launch_url']
    list_filter = ['has_grade', 'created_at']
    fields = ['name', 'launch_url', 'platform_config', 'has_grade', 'max_grade', 'assessment', 'created_at']

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['platform_config']
        return self.readonly_fields

@admin.register(CourseRating)
class CourseRatingAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'rating', 'created_at')
    search_fields = ('user__username', 'course__course_name')
    
    # Menentukan jumlah item per halaman
    list_per_page = 20 

admin.site.register(Hashtag)
admin.site.register(BlacklistedKeyword)
admin.site.register(UserProfile)
@admin.register(SosPost)
class SosPostAdmin(admin.ModelAdmin):
    list_display = ('user', 'content', 'created_at',  'deleted')
    search_fields = ('user__username', 'content')
    list_filter = ('deleted', 'created_at')
    ordering = ('-created_at',)
    list_per_page = 10

class CourseAdmin(ImportExportModelAdmin):
    list_display = ('course_name', 'course_number', 'course_run', 'category', 'level')  # Adjust based on your fields
    search_fields = ['course_name', 'course_number']  # Optional: add search functionality
    list_per_page = 10

# Register the model with the admin site using the ImportExportModelAdmin
admin.site.register(Course, CourseAdmin)

@admin.register(CalculateAdminPrice)
class CalculateAdminPriceAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'created_at')  # Menampilkan kolom utama di list view
    search_fields = ('name',)  # Memungkinkan pencarian berdasarkan nama
    list_filter = ('created_at',)  # Filter berdasarkan tanggal dibuat
    ordering = ('-created_at',)  # Urutkan dari yang terbaru
    list_per_page = 10

admin.site.register(models.Section)
class PartnerAdmin(admin.ModelAdmin):
    autocomplete_fields = ['user','author']  # This will apply autocomplete to the 'user' ForeignKey field
    search_fields = ['name', 'abbreviation', 'user__username']
    list_per_page = 10
admin.site.register(Partner, PartnerAdmin)

class CategoryAdmin(admin.ModelAdmin):
    # Mengatur jumlah item yang ditampilkan per halaman (pagination)
    list_per_page = 10  # Atur jumlah kategori yang ingin ditampilkan per halaman

    # Menambahkan fitur pencarian berdasarkan nama kategori dan slug
    search_fields = ['name', 'slug']

    # Menambahkan kolom yang akan ditampilkan di halaman daftar admin
    list_display = ('name', 'slug', 'user')

    # Menambahkan filter untuk memudahkan penyaringan data
    list_filter = ('user',)

# Daftarkan model Category di admin dengan konfigurasi yang sudah diatur
admin.site.register(Category, CategoryAdmin)
admin.site.register(models.Instructor)
admin.site.register(models.TeamMember)
admin.site.register(GradeRange)

admin.site.register(Enrollment)
admin.site.register(PricingType)
admin.site.register(CoursePrice)
admin.site.register(CourseStatusHistory)
admin.site.register(CourseStatus)
admin.site.register(AssessmentRead)
admin.site.register(QuestionAnswer)
# Register your models here.
class MicroCredentialAdmin(admin.ModelAdmin):
    # Specify the fields to display in the list view
    list_display = ('title', 'status', 'start_date', 'end_date', 'min_total_score', 'category', 'author')
    # Add search functionality for specific fields (e.g., title, status, etc.)
    search_fields = ('title', 'slug', 'description')
    # Enable filtering by status and category
    list_filter = ('status', 'category')
    # Allow ordering by start date and end date
    ordering = ('start_date',)

    # Optionally, you can add inline editing for related models, for example, required courses
    filter_horizontal = ('required_courses',)  # To make 'required_courses' display as a filterable horizontal list
    list_per_page = 10

# Register the model with the custom admin class
admin.site.register(MicroCredential, MicroCredentialAdmin)
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
    list_per_page = 10
# Mendaftarkan model Submission di admin
admin.site.register(Submission, SubmissionAdmin)
admin.site.register(PeerReview)
admin.site.register(AssessmentScore)

@admin.register(Material)

class MaterialAdmin(admin.ModelAdmin):

    list_display = ('title', 'section', 'created_at')

    list_filter = ('section',)
    list_per_page = 10

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
    list_per_page = 10