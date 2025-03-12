# models.py
from django.db import models
from authentication.models import CustomUser, Universiti
from autoslug import AutoSlugField
from django.utils.text import slugify
import os
import re
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.db.models import Sum
from datetime import date
from decimal import Decimal
from django.core.validators import MinValueValidator
import bleach
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    blocked_until = models.DateTimeField(null=True, blank=True)
    def is_blocked(self):
        return self.blocked_until and self.blocked_until > timezone.now()

class BlacklistedKeyword(models.Model):
    keyword = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.keyword
    
class Partner(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE,related_name="partner_user")  # Add this line to associate partners with users
    name = models.ForeignKey(Universiti, on_delete=models.CASCADE,related_name="partner_univ")
   
    phone = models.CharField(max_length=50,null=True, blank=True)
    address = models.TextField(max_length=200,null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    tax = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Tax (%)", default=0.00)
    iceiprice = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="share icei (%)", default=0.00)
    account_number = models.CharField(max_length=20, null=True, blank=True)  # Account number as a string
    account_holder_name = models.CharField(max_length=250,null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    logo = models.ImageField(upload_to='logos/',null=True, blank=True)
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="partner_author") 
    created_ad = models.DateTimeField(auto_now_add=True)  # Automatically set when the ad is created
    updated_ad = models.DateTimeField(auto_now=True) 

    def __str__(self):
        return f"{self.name}"
    class Meta:
        indexes = [
            models.Index(fields=['user'])
    ]
        

    def delete_old_logo(self):
        if self.pk:  # Hanya jika instance sudah ada di database
            old_logo = Partner.objects.filter(pk=self.pk).values_list('logo', flat=True).first()
            if old_logo and old_logo != self.logo.name:
                old_logo_path = os.path.join(settings.MEDIA_ROOT, old_logo)
                if os.path.exists(old_logo_path):
                    os.remove(old_logo_path)

    def save(self, *args, **kwargs):
        self.delete_old_logo()  # Hapus logo lama sebelum menyimpan
        super().save(*args, **kwargs)


class Instructor(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="instructors")
    bio = models.TextField()
    tech = models.CharField(max_length=255)
    expertise = models.CharField(max_length=255)
    experience_years = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    agreement = models.BooleanField(default=False, help_text="Check if the user agrees to the terms and conditions")
    provider =models.ForeignKey(Partner,on_delete=models.CASCADE,related_name='instructors')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} "
    
class Category(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)  # Add this line to associate partners with users
    name = models.CharField(max_length=250)

    def __str__(self):
        return self.name



class CourseStatus(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('curation', 'Curation'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    manual_message = models.TextField(blank=True, null=True)  # Pesan manual terkait status
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_status_display()} - {self.manual_message[:50]}"

    def set_message(self, message):
        """Menambahkan pesan manual pada status ini."""
        self.manual_message = message
        self.save()


class CourseStatusHistory(models.Model):
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name="status_history")
    status = models.CharField(max_length=20, choices=CourseStatus.STATUS_CHOICES)
    manual_message = models.TextField(blank=True, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)  # Waktu perubahan status
    changed_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)  # Pengguna yang membuat perubahan

    def __str__(self):
        return f"Course {self.course.course_name} - Status: {self.status} at {self.changed_at}"

    class Meta:
        ordering = ['-changed_at']  # Urutkan berdasarkan waktu perubahan terbaru


class Course(models.Model):
    course_name = models.CharField(max_length=250)
    course_number = models.CharField(max_length=250, blank=True)
    course_run = models.CharField(max_length=250, blank=True)
    slug = models.CharField(max_length=250, blank=True)
    org_partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name="courses")
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name="courses", null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="category_courses")
    level = models.CharField(max_length=10, choices=[('basic', 'Basic'), ('middle', 'Middle'), ('advanced', 'Advanced')], default='basic', null=True, blank=True)
    status_course = models.ForeignKey(CourseStatus, on_delete=models.CASCADE, related_name="courses")  # Hubungkan dengan CourseStatus
    created_at = models.DateTimeField(auto_now_add=True)
    edited_on = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='courses/', blank=True, null=True)
    link_video = models.URLField(blank=True, null=True)
    description = models.TextField()
    sort_description = models.CharField(max_length=150, null=True, blank=True)
    hour = models.CharField(max_length=2, null=True, blank=True)
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    language = models.CharField(max_length=10, choices=[('en', 'English'), ('id', 'Indonesia'), ('fr', 'French'), ('de', 'German')], default='en')
    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)
    start_enrol = models.DateField(null=True)
    end_enrol = models.DateField(null=True)

    def __str__(self):
        return f"{self.course_name}"

    def delete_old_image(self):
        """Hapus gambar lama jika sudah diganti."""
        if self.pk:  # Pastikan instance ada di database
            old_image = Course.objects.filter(pk=self.pk).values_list('image', flat=True).first()
            if old_image and old_image != self.image.name:
                old_image_path = os.path.join(settings.MEDIA_ROOT, old_image)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)

    def save(self, *args, **kwargs):
        self.delete_old_image()  # Hapus gambar lama sebelum menyimpan data baru
        super().save(*args, **kwargs)

    def is_enrollment_open(self):
        """ Cek apakah periode enrollment masih terbuka """
        today = date.today()
        return self.start_enrol <= today <= self.end_enrol if self.start_enrol and self.end_enrol else False

    def enroll_user(self, user):
        """ Mendaftarkan user ke dalam course jika pendaftaran masih terbuka """
        if not self.is_enrollment_open():
            return {"status": "error", "message": "Enrollment is closed for this course."}

        enrollment, created = Enrollment.objects.get_or_create(user=user, course=self)
        if created:
            return {"status": "success", "message": "Successfully enrolled in the course."}
        else:
            return {"status": "info", "message": "You are already enrolled in this course."}

    def move_to_curation(self, message=None, user=None):
        if self.status_course.status != 'draft':
            raise ValidationError('Course is not in the correct stage for curation.')
        self.status_course.status = 'curation'
        if message:
            self.status_course.set_message(message)  # Set pesan manual
        self.status_course.save()

        # Simpan riwayat perubahan status
        CourseStatusHistory.objects.create(course=self, status=self.status_course.status, manual_message=message, changed_by=user)

        return {"status": "info", "message": "The course is now under curation.", "manual_message": self.status_course.manual_message}

    def publish_course(self, message=None, user=None):
        if self.status_course.status != 'curation':
            raise ValidationError('Course is not in the correct stage for publishing.')
        self.status_course.status = 'published'
        if message:
            self.status_course.set_message(message)  # Set pesan manual
        self.status_course.save()

        # Simpan riwayat perubahan status
        CourseStatusHistory.objects.create(course=self, status=self.status_course.status, manual_message=message, changed_by=user)

        return {"status": "success", "message": "The course has been successfully published.", "manual_message": self.status_course.manual_message}

    def archive_course(self, message=None, user=None):
        if self.status_course.status != 'published':
            raise ValidationError('Course cannot be archived before being published.')
        self.status_course.status = 'archived'
        if message:
            self.status_course.set_message(message)  # Set pesan manual
        self.status_course.save()

        # Simpan riwayat perubahan status
        CourseStatusHistory.objects.create(course=self, status=self.status_course.status, manual_message=message, changed_by=user)

        return {"status": "info", "message": "The course has been archived.", "manual_message": self.status_course.manual_message}
    
    






    
class PricingType(models.Model):
    name = models.CharField(max_length=50, unique=True)  # Nama pricing type (contoh: 'Regular Price', 'Discount')
    description = models.TextField(blank=True, null=True)  # Deskripsi opsional
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
class CalculateAdminPrice(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Pricing Type")  
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Amount (IDR)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")

    def __str__(self):
        return f"{self.name} - IDR {self.amount:,.2f}"
    
class CoursePrice(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="prices")
    price_type = models.ForeignKey(PricingType, on_delete=models.CASCADE, related_name="course_prices")
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name="course_prices")

    # Harga dari Partner
    partner_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Partner Price", default=Decimal('0.00'))

    # Diskon dari Partner
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name="Discount (%)")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Discount Amount")  

    # Admin Fee / ICE Share
    ice_share_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('20.00'), verbose_name="ICE Share (%)")  # Nama lebih jelas
    admin_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Admin Fee")
    ice_share_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="ICE Share Value")  # Untuk nilai final

    # Pajak & PPN
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Tax (%)")
    ppn_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('11.00'), verbose_name="PPN Rate (%)")  # Nama lebih jelas
    ppn = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="PPN")  # Nilai PPN setelah dihitung

    # Perhitungan Harga
    sub_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Sub Total")  
    portal_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Portal Price")  
    normal_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Normal Price")  

    # Biaya Platform & Voucher dari CalculateAdminPrice
    calculate_admin_price = models.ForeignKey(CalculateAdminPrice, on_delete=models.SET_NULL, null=True, blank=True, related_name="course_prices")
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Platform Fee")  
    voucher = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Voucher")

    # Total yang dibayar user
    user_payment = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="User Payment")  
    
    # Pendapatan Partner & ICE
    partner_earning = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Partner Earning")  
    ice_earning = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="ICE Earning")  

    # Timestamp untuk audit
    created_at = models.DateTimeField(auto_now_add=True)

    def calculate_prices(self):
        """
        Menghitung semua harga berdasarkan rumus yang diberikan.
        """

        # ✅ 1. Pastikan `ice_share_rate` dan `ppn_rate` otomatis dari Partner
        if self.partner:
            self.ice_share_rate = self.partner.iceiprice  # ✅ Ambil otomatis dari Partner
            self.ppn_rate = self.partner.tax  # ✅ Ambil otomatis dari Partner

        normal_price = Decimal(self.partner_price)  # Harga awal dari partner
        discount_percent = Decimal(self.discount_percent) / Decimal('100')
        ice_share_percent = Decimal(self.ice_share_rate) / Decimal('100')  # Sekarang otomatis dari Partner
        ppn_percent = Decimal(self.ppn_rate) / Decimal('100')  # Sekarang otomatis dari Partner

        # ✅ 2. Hitung Diskon (Nilai dalam angka)
        self.discount_amount = normal_price * discount_percent

        # ✅ 3. Hitung Net Price (Harga setelah Diskon)
        net_price = normal_price - self.discount_amount  

        # ✅ 4. Hitung Admin Fee (ICE Share % dari Net Price)
        self.admin_fee = net_price * ice_share_percent

        # ✅ 5. Hitung Sub Total
        self.sub_total = net_price + self.admin_fee

        # ✅ 6. Hitung PPN
        self.ppn = self.sub_total * ppn_percent

        # ✅ 7. Hitung Portal Price
        self.portal_price = self.sub_total + self.ppn

        # ✅ 8. Hitung Normal Price (Diperbarui dengan Diskon)
        self.normal_price = self.portal_price + (normal_price * discount_percent)

        # ✅ 9. Hitung Partner Earning
        self.partner_earning = self.partner_price - self.discount_amount

        # ✅ 10. Hitung ICE Earning
        self.ice_earning = self.admin_fee - self.voucher

        # ✅ 11. Ambil `platform_fee` & `voucher` dari `CalculateAdminPrice`
        platform_fee_entry = CalculateAdminPrice.objects.filter(name__iexact="Platform Fee").first()
        voucher_entry = CalculateAdminPrice.objects.filter(name__iexact="Voucher").first()

        self.platform_fee = platform_fee_entry.amount if platform_fee_entry else Decimal('0.00')
        self.voucher = voucher_entry.amount if voucher_entry else Decimal('0.00')

        # ✅ 12. Hitung User Payment
        self.user_payment = self.portal_price - self.voucher + self.platform_fee




    def save(self, *args, **kwargs):
        """
        Pastikan `ice_share_rate` dan `ppn_rate` otomatis dari Partner sebelum menyimpan.
        """
        if self.partner:
            self.ice_share_rate = self.partner.iceiprice  # Ambil ICE Share dari Partner
            self.ppn_rate = self.partner.tax  # Ambil PPN dari Partner

        self.calculate_prices()  # Pastikan harga dihitung sebelum disimpan
        super().save(*args, **kwargs)  # Simpan ke database

    def __str__(self):
        return f"{self.course} - {self.price_type.name} - {self.partner_price}"
    
class Subscription(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    subscription_type = models.CharField(
        max_length=50,
        choices=[('monthly', 'Monthly'), ('yearly', 'Yearly'), ('course_specific', 'Course-Specific')],
        default='monthly'
    )

    def check_expiration(self):
        if self.end_date < timezone.now():
            self.is_active = False
            self.save()

    def __str__(self):
        return f"{self.user.username} subscription ({self.subscription_type}) active from {self.start_date} to {self.end_date}"

class Enrollment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} enrolled in {self.course.course_name}"
    
    class Meta:
        unique_together = ('user', 'course')  # User hanya bisa mendaftar 1x ke tiap course

class TeamMember(models.Model):

    course = models.ForeignKey(Course, related_name='team_members', on_delete=models.CASCADE)

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)  # Change name to user

    def __str__(self):

        return f"{self.user.username}"


    def __str__(self):

        return f"{self.course} - {self.user}"

class Section(models.Model):
    parent = models.ForeignKey('self', related_name='children', on_delete=models.CASCADE, blank = True, null=True)
    title = models.CharField(max_length=100) 
    slug = AutoSlugField(populate_from='title', unique=True, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    courses=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='sections')

    def __str__(self):
        return self.title

    class Meta:
        #enforcing that there can not be two categories under a parent with same slug
        
        # __str__ method elaborated later in post.  use __unicode__ in place of

        unique_together = ('slug', 'parent',)    
        verbose_name_plural = "section"     

    def __str__(self):                           
        full_path = [self.title]                  
        k = self.parent
        while k is not None:
            full_path.append(k.title)
            k = k.parent
        return ' -> '.join(full_path[::-1])  


class Material(models.Model):

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='materials')

    title = models.CharField(max_length=100)

    description = models.TextField(blank=True, null=True)

    

    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):

        return self.title


    class Meta:

        verbose_name_plural = "materials"

class GradeRange(models.Model):
    name = models.CharField(max_length=255)  # Nama rentang nilai (misalnya "A", "B+")
    min_grade = models.DecimalField(max_digits=5, decimal_places=2)  # Nilai minimum untuk rentang
    max_grade = models.DecimalField(max_digits=5, decimal_places=2)  # Nilai maksimum untuk rentang
    course = models.ForeignKey(Course, related_name='grade_ranges', on_delete=models.CASCADE)  # Menghubungkan rentang nilai dengan mata pelajaran
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.min_grade} - {self.max_grade})"
    
    # Validasi untuk memastikan min_grade selalu kurang dari atau sama dengan max_grade
    def save(self, *args, **kwargs):
        if self.min_grade > self.max_grade:
            raise ValueError("min_grade tidak bisa lebih besar dari max_grade")
        super().save(*args, **kwargs)

class MicroCredential(models.Model):
    title = models.CharField(max_length=250)
    slug = models.CharField(max_length=250, blank=True)
    description = models.TextField()
    required_courses = models.ManyToManyField(Course, related_name="microcredentials")
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('inactive', 'Inactive'), ('draft', 'Draft')],
        default='draft'
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    image = models.ImageField(upload_to='microcredentials/', blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="microcredentials", null=True, blank=True)
    min_total_score = models.FloatField(default=0.0, help_text="Total minimum score required across all courses")
    
    created_at = models.DateTimeField(auto_now_add=True)
    edited_on = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    def __str__(self):
        return self.title

    def get_min_score(self, course):
        grade_ranges = GradeRange.objects.filter(course=course).order_by('min_grade')
        if grade_ranges.exists():
            return grade_ranges.first().min_grade
        return 0.0
    def enroll_user(self, user):
        """Mendaftarkan pengguna ke microcredential dan semua kursus terkait."""
        from .models import Enrollment, MicroCredentialEnrollment
        
        # Daftarkan ke microcredential
        enrollment, created = MicroCredentialEnrollment.objects.get_or_create(
            user=user,
            microcredential=self
        )
        
        # Daftarkan ke semua required_courses
        for course in self.required_courses.all():
            Enrollment.objects.get_or_create(
                user=user,
                course=course
            )
        return enrollment, created
    
class UserMicroProgress(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="micro_progress")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="user_progress")
    microcredential = models.ForeignKey(MicroCredential, on_delete=models.CASCADE, related_name="user_progress")
    progress = models.FloatField(default=0.0)  # Persentase progres (0-100)
    score = models.FloatField(default=0.0)    # Skor akhir course
    completed = models.BooleanField(default=False)  # True kalau course selesai
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'course', 'microcredential')  # Pastikan unik per user-course-micro

    def __str__(self):
        return f"{self.user} - {self.course} ({self.microcredential})"

class UserMicroCredential(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="microcredentials")
    microcredential = models.ForeignKey(MicroCredential, on_delete=models.CASCADE, related_name="users")
    completed = models.BooleanField(default=False)  # True kalau semua course lulus
    certificate_id = models.CharField(max_length=250, blank=True, null=True)  # ID sertifikat (PDF atau blockchain)
    issued_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.microcredential}"
    

class Assessment(models.Model):
    name = models.CharField(max_length=255)
    section = models.ForeignKey(Section, related_name="assessments", on_delete=models.CASCADE)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Bobot untuk penilaian ini
    description = models.TextField(blank=True, null=True)
    flag = models.BooleanField(default=False)
    duration_in_minutes = models.IntegerField(null=True, blank=True)
   
    grade_range = models.ForeignKey(GradeRange, related_name="assessments", on_delete=models.SET_NULL, null=True, blank=True)  # Menghubungkan dengan rentang nilai
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} "
    def save(self, *args, **kwargs):
        # Hapus validasi bobot dari sini jika sudah dilakukan di views
        # if self.weight > 100:  # Removed because validation is in views
        #     raise ValueError("Total bobot untuk penilaian dalam section ini tidak boleh melebihi 100")
        
        super().save(*args, **kwargs)

class AssessmentSession(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE)
    start_time = models.DateTimeField()  # Waktu mulai ujian
    end_time = models.DateTimeField()  # Waktu selesai ujian, dihitung berdasarkan durasi

    def save(self, *args, **kwargs):
        # Menghitung waktu berakhir berdasarkan waktu mulai dan durasi
        self.end_time = self.start_time + timedelta(minutes=self.assessment.duration_in_minutes)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sesi ujian {self.assessment.name} untuk {self.user.username}"

class Question(models.Model):
    assessment = models.ForeignKey(Assessment, related_name="questions", on_delete=models.CASCADE)
    text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text
    # Method to get the correct choice
    def correct_choice(self):
        return self.choices.filter(is_correct=True).first()

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.TextField(blank=True, null=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text
    
class AskOra(models.Model):
    assessment = models.ForeignKey(Assessment, related_name='ask_oras', on_delete=models.CASCADE)
    title = models.CharField(max_length=200, null=True, blank=True)
    question_text = models.TextField()
    response_deadline = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    def is_responsive(self):
        return self.response_deadline > timezone.now()
    def __str__(self):
        return f"ask {self.title} "

class Submission(models.Model):
    askora = models.ForeignKey(
        'AskOra',  # Menghubungkan ke model AskOra
        related_name='submissions',
        on_delete=models.CASCADE
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)  # Peserta yang mengirimkan jawaban
    answer_text = models.TextField()  # Jawaban teks dari peserta
    answer_file = models.FileField(upload_to='submissions/', blank=True, null=True)  # Jawaban file jika diperlukan
    score = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])  # Nilai jawaban
    submitted_at = models.DateTimeField(auto_now_add=True)  # Waktu pengiriman jawaban



    
        
    

    
class PeerReview(models.Model):
    submission = models.ForeignKey(Submission, related_name='peer_reviews', on_delete=models.CASCADE)
    reviewer = models.ForeignKey(CustomUser, on_delete=models.CASCADE)  # User yang memberikan review
    score = models.IntegerField(choices=[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)])  # Skor 1-5
    comment = models.TextField(blank=True, null=True)  # Komentar dari reviewer
    weight = models.DecimalField(max_digits=3, decimal_places=2, default=1.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('submission', 'reviewer')  # Satu reviewer hanya bisa memberikan review sekali per submission

    def __str__(self):
        return f"Review by {self.reviewer.username} for {self.submission.user.username}'s submission"
    
class AssessmentScore(models.Model):
    submission = models.ForeignKey(Submission, related_name='assessment_scores', on_delete=models.CASCADE)
    final_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Skor akhir
    created_at = models.DateTimeField(auto_now_add=True)

    def calculate_final_score(self):
        peer_reviews = self.submission.peer_reviews.all()
        if peer_reviews:
            total_score = sum(review.score * review.weight for review in peer_reviews)
            peer_review_count = peer_reviews.count()
            avg_peer_score = total_score / peer_review_count
        else:
            avg_peer_score = 0
        
        # Skor jawaban peserta, misalnya 50% bobot untuk jawaban otomatis
        participant_score = 5  # Misalnya nilai maksimum 5

        # Menghitung skor akhir dengan bobot
        self.final_score = (participant_score * 0.5) + (avg_peer_score * 0.5)
        self.save()

    def __str__(self):
        # Mengakses assessment melalui askora
        return f"Score for {self.submission.user.username} in {self.submission.askora.assessment.name}"

    
class Score(models.Model):
    user = models.CharField(max_length=255)  # Username or session key
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='scores')  # Relate scores to a course
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='scores', null=True, blank=True)  # Optional relation to a section
    score = models.IntegerField()
    total_questions = models.IntegerField()
    grade = models.CharField(max_length=2, blank=True)
    time_taken = models.DurationField(null=True, blank=True)  # Store quiz duration
    date = models.DateTimeField(auto_now_add=True)
    submitted = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user} - {self.course} - {self.score}/{self.total_questions} ({self.grade})"
    
class AttemptedQuestion(models.Model):
    user = models.CharField(max_length=255)  # Username or anonymous identifier
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='attempted_questions')  # Relate to a course
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='attempted_questions', null=True, blank=True)  # Optional relation to a section
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='attempts')  # Relate to a question
    selected_choice = models.ForeignKey(Choice, on_delete=models.CASCADE)
    is_correct = models.BooleanField()
    date_attempted = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.course} - {self.question.text} - {'Correct' if self.is_correct else 'Incorrect'}"
    

class CourseProgress(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    progress = models.FloatField(default=0)  # Percentage completion of the course
    progress_percentage = models.FloatField(default=0)  # New field to store percentage progress
    grade = models.ForeignKey(GradeRange, null=True, blank=True, on_delete=models.SET_NULL)
    def __str__(self):
        return f"{self.user.username} - {self.course.course_name}"

    @classmethod
    def get_user_course_progress(cls, user, course):
        try:
            progress = cls.objects.get(user=user, course=course).progress
            return progress
        except cls.DoesNotExist:
            return 0

        
class MaterialRead(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)  # Time when the material was read

    class Meta:
        unique_together = ('user', 'material')  # Ensure that each user can mark a material as read only once

    def __str__(self):
        return f"{self.user.username} - {self.material.title} - Read on {self.read_at}"
class AssessmentRead(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE)
    completed_at = models.DateTimeField(auto_now_add=True)  # Time when the assessment was completed

    class Meta:
        unique_together = ('user', 'assessment')  # Ensure that each user can mark an assessment as completed only once

    def __str__(self):
        return f"{self.user.username} - {self.assessment.name} - Completed on {self.completed_at}"

class QuestionAnswer(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choice = models.ForeignKey(Choice, on_delete=models.CASCADE)  # Menyimpan pilihan yang dipilih
    answered_at = models.DateTimeField(auto_now_add=True)  # Waktu saat soal dijawab

    class Meta:
        unique_together = ('user', 'question')  # Pastikan setiap user hanya bisa menjawab sekali untuk setiap pertanyaan

    def __str__(self):
        return f"{self.user.username} - Answered {self.question.text} with {self.choice.text} on {self.answered_at}"

class Comment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField(blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    material = models.ForeignKey('Material', on_delete=models.CASCADE)
    likes = models.IntegerField(default=0)  # Jumlah like
    dislikes = models.IntegerField(default=0)  # Jumlah dislike
    parent=models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=['material']),
        ]
    
    def __str__(self):
        return f'Comment by {self.user.username} on {self.created_at}'
    def contains_blacklisted_keywords(self):
        """Check if the comment contains any blacklisted keywords."""
        blacklisted_keywords = [
            'gratis', 'promo', 'diskon', 'belanja', 'jualan', 'poker', 'judi', 
            'kredit', 'utang', 'deposito', 'investasi', 'uang', 'tawaran', 'hadiah', 
            'pemenang', 'hack', 'phishing', 'penipuan', 'melanggar', 'bocor','kunci jawaban','email','0857',
             '0858','0859','021','0812','0813','0811','0856','@gmail','@', 'penjualan'
        ]
        for keyword in blacklisted_keywords:
            if keyword.lower() in self.content.lower():
                return True
        return False
    

class CourseComment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField(blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    course = models.ForeignKey('Course', on_delete=models.CASCADE)
    likes = models.IntegerField(default=0)  # Jumlah like
    dislikes = models.IntegerField(default=0)  # Jumlah dislike
    parent=models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE)
    def is_spam(self):
        # Membatasi komentar dengan interval 1 menit
        last_comment_time = CourseComment.objects.filter(user=self.user).order_by('-created_at').first()
        if last_comment_time:
            time_difference = timezone.now() - last_comment_time.created_at
            if time_difference < timedelta(minutes=1):  # Cooldown 1 menit
                return True
        return False

    class Meta:
        indexes = [
            models.Index(fields=['course']),
        ]

    def __str__(self):
        return f'Comment by {self.user.username} on {self.created_at}'
    def contains_blacklisted_keywords(self):
        """Memeriksa apakah konten mengandung kata-kata yang diblacklist."""
        blacklisted_keywords = BlacklistedKeyword.objects.values_list('keyword', flat=True)
        for keyword in blacklisted_keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', self.content.lower()):
                return True
        return False
    
class MicroCredentialEnrollment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="microcredential_enrollments")
    microcredential = models.ForeignKey('MicroCredential', on_delete=models.CASCADE, related_name="enrollments")
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'microcredential')  # Pastikan pengguna hanya terdaftar sekali per microcredential

    def __str__(self):
        return f"{self.user.username} enrolled in {self.microcredential.title}"
    




class SosPost(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    deleted = models.BooleanField(default=False)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)


    def clean_content(self):
        """Membersihkan konten dari tag HTML berbahaya."""
        return bleach.clean(self.content)

    def clean(self):
        """Validasi sebelum simpan."""
        self.content = self.clean_content()
        if len(self.content) > 150:
            raise ValidationError("Konten terlalu panjang, maksimum 150 karakter.")
        if self.contains_blacklisted_keywords():
            raise ValidationError("Konten mengandung kata-kata yang dilarang.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        # Simpan hashtag setelah post disimpan
        self.save_hashtags()

    def contains_blacklisted_keywords(self):
        blacklisted_keywords = BlacklistedKeyword.objects.values_list('keyword', flat=True)
        for keyword in blacklisted_keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', self.content.lower()):
                return True
        return False

    def get_hashtags(self):
        """Ekstrak hashtag dari konten."""
        return re.findall(r'#\w+', self.content)

    def save_hashtags(self):
        """Simpan hashtag ke model Hashtag."""
        hashtags = self.get_hashtags()
        for tag in hashtags:
            hashtag, created = Hashtag.objects.get_or_create(name=tag[1:].lower())
            hashtag.posts.add(self)

    def retweet_post(self, user):
        if self.retweet:
            return None
        retweet_content = f"Retweeted: {self.content}"
        return SosPost.objects.create(
            user=user,
            content=retweet_content[:150],  # Pastikan sesuai batas
            retweet=self
        )

    def delete_post(self):
        self.deleted = True
        self.save()

    def __str__(self):
        return f'Post by {self.user.username} on {self.created_at}'

class Hashtag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    posts = models.ManyToManyField(SosPost, related_name='hashtags')

class Like(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    post = models.ForeignKey(SosPost, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')  # Memastikan kombinasi user dan post unik