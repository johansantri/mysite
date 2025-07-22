from django.contrib import admin
from . import models 
from .models import  InstructorCertificate,LTIResult,LTIExternalTool1,MicroClaim,UserMicroProgress,MicroCredentialComment,Certificate,Submission,CourseRating,UserProfile,Hashtag,SosPost,AskOra,BlacklistedKeyword, PeerReview,MicroCredential, AssessmentScore,Partner,Comment,CourseComment,AssessmentRead,Choice,AssessmentSession,QuestionAnswer,CourseStatusHistory,CourseStatus,CourseProgress,MaterialRead,CalculateAdminPrice,Universiti,GradeRange,Enrollment,PricingType,CoursePrice, Instructor, Category, Course, TeamMember, Section, Material,Question, Choice, Score, AttemptedQuestion,Assessment
from import_export.admin import ImportExportModelAdmin
from django.utils.html import format_html

@admin.register(InstructorCertificate)
class InstructorCertificateAdmin(admin.ModelAdmin):
    list_display = ('instructor', 'course', 'issued_at', 'partner', 'certificate_file')
    search_fields = ('instructor__full_name', 'course__course_name')
    list_filter = ('partner', 'issued_at')
    readonly_fields = ('issued_at',)


@admin.register(LTIResult)
class LTIResultAdmin(admin.ModelAdmin):
    list_display = (
        'user_full_name',
        'assessment_title',
        'score_display',
        'consumer_key',
        'created_at',
        'last_sent_at',
    )
    list_filter = ('consumer_key', 'created_at', 'last_sent_at')
    search_fields = ('user__username', 'user__email', 'assessment__title', 'result_sourcedid')
    readonly_fields = ('created_at', 'last_sent_at')
    ordering = ('-created_at',)

    def user_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    user_full_name.short_description = "User"

    def assessment_title(self, obj):
        return obj.assessment.name
    assessment_title.short_description = "Assessment"

    def score_display(self, obj):
        return f"{obj.score:.2f}" if obj.score is not None else "-"
    score_display.short_description = "Score"

@admin.register(LTIExternalTool1)
class LTIExternalTool1Admin(admin.ModelAdmin):
    list_display = ['tool_name', 'assessment', 'launch_url', 'tool_url', 'consumer_key', 'created_at']
    search_fields = ['tool_name', 'consumer_key', 'launch_url']
    list_filter = ['created_at']
    readonly_fields = ['created_at']
    fieldsets = (
        (None, {
            'fields': ('tool_name', 'assessment', 'launch_url', 'tool_url', 'consumer_key', 'shared_secret', 'custom_parameters')
        }),
        ('Info', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

# Kelas admin untuk model MicroClaim
class MicroClaimAdmin(admin.ModelAdmin):
    list_display = ('user', 'microcredential', 'claim_date', 'certificate_id', 'verified')  # Menampilkan kolom yang ingin ditampilkan di daftar
    search_fields = ('user__username', 'microcredential__title', 'certificate_id')  # Kolom yang bisa dicari
    list_filter = ('verified', 'claim_date')  # Filter untuk mempermudah pencarian
    ordering = ('-claim_date',)  # Mengurutkan berdasarkan tanggal klaim terbaru

    # Opsi untuk memverifikasi klaim langsung dari admin panel
    actions = ['verify_claim_action']

    def verify_claim_action(self, request, queryset):
        # Menambahkan aksi untuk memverifikasi klaim langsung dari admin
        updated_count = queryset.update(verified=True)
        self.message_user(request, f'{updated_count} klaim telah diverifikasi.')
    verify_claim_action.short_description = "Verifikasi klaim yang dipilih"

# Mendaftarkan model MicroClaim dan kelas admin-nya
admin.site.register(MicroClaim, MicroClaimAdmin)

class UserMicroProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'microcredential', 'progress', 'score', 'completed', 'completed_at')
    list_filter = ('course', 'microcredential', 'completed')  # Filter berdasarkan course, microcredential, atau status selesai
    search_fields = ('user__username', 'course__name', 'microcredential__name')  # Mencari berdasarkan username, course, atau microcredential
    ordering = ('-completed_at',)  # Urutkan berdasarkan waktu penyelesaian, yang terbaru lebih dulu
    date_hierarchy = 'completed_at'  # Memungkinkan pemfilteran berdasarkan tanggal

    # Jika Anda ingin menambahkan form untuk mengatur beberapa nilai terkait, bisa menambahkan fieldsets atau readonly_fields
    # fieldsets = (
    #     (None, {
    #         'fields': ('user', 'course', 'microcredential', 'progress', 'score', 'completed', 'completed_at')
    #     }),
    # )
    
    # Misalnya, hanya bisa mengedit status progress di admin panel:
    readonly_fields = ('user', 'course', 'microcredential', 'completed_at')  # Contoh readonly fields

# Mendaftarkan model UserMicroProgress ke panel admin
admin.site.register(UserMicroProgress, UserMicroProgressAdmin)

class MicroCredentialCommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'microcredential', 'created_at', 'likes', 'dislikes', 'is_spam', 'parent')  # Menampilkan field yang relevan di daftar admin
    list_filter = ('microcredential', 'created_at', 'likes', 'dislikes')  # Filter berdasarkan kolom ini
    search_fields = ('user__username', 'content', 'microcredential__title')  # Mencari berdasarkan kolom ini
    date_hierarchy = 'created_at'  # Menyediakan filter berdasarkan tanggal
    ordering = ('-created_at',)  # Urutkan komentar terbaru ke atas
    raw_id_fields = ('user', 'microcredential')  # Gunakan raw_id untuk pemilihan user dan microcredential (agar lebih efisien)
    fields = ('user', 'content', 'microcredential', 'parent', 'likes', 'dislikes', 'created_at')  # Menentukan urutan field yang ditampilkan saat mengedit komentar
    readonly_fields = ('created_at',)  # Membuat field 'created_at' menjadi hanya baca
    
    def is_spam(self, obj):
        return obj.is_spam()
    is_spam.boolean = True  # Menampilkan checkbox untuk spam di admin panel

# Registrasi model dan admin
admin.site.register(MicroCredentialComment, MicroCredentialCommentAdmin)








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
@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    search_fields = ['title', 'description'] 
admin.site.register(AttemptedQuestion)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ('user', 'score', 'total_questions', 'grade', 'date')
    list_filter = ('grade', 'date')
    list_per_page = 10


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    # Fields to display in the list view
    list_display = ('certificate_id', 'user', 'course', 'issue_date', 'total_score', 'partner', 'created_at')
    
    # Fields that can be searched
    search_fields = ('certificate_id', 'user__username', 'course__course_name')
    
    # Filters for the sidebar
    list_filter = ('issue_date', 'partner', 'created_at')
    
    # Fields to display in the detail view (form)
    fields = ('certificate_id', 'user', 'course', 'issue_date', 'total_score', 'partner', 'created_at')
    
    # Make these fields read-only in the admin
    readonly_fields = ('certificate_id', 'created_at')
    
    # Enable clickable links for user and course
    list_display_links = ('certificate_id',)
    
    # Order the list by issue date (newest first)
    ordering = ('-issue_date',)
    
    # Customize how related fields are displayed
    def get_user(self, obj):
        return obj.user.username
    get_user.short_description = 'User'
    
    def get_course(self, obj):
        return obj.course.course_name
    get_course.short_description = 'Course'
    
    # Optional: Add pagination to the list view
    list_per_page = 25