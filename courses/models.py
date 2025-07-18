# models.py
from django.db import models
from authentication.models import CustomUser, Universiti
from licensing.models import License
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
import datetime
from decimal import Decimal
from django.core.validators import MinValueValidator
import bleach
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.files.storage import default_storage
import uuid
from django.contrib.postgres.fields import JSONField 
from payments.models import Payment
from licensing.models import Invitation
import logging
from django.db.models import Count
import json
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jwcrypto import jwk

logger = logging.getLogger(__name__)

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
    bank_name = models.CharField(max_length=250,null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    logo = models.ImageField(upload_to='logos/',null=True, blank=True)
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="partner_author") 
    created_ad = models.DateTimeField(auto_now_add=True)  # Automatically set when the ad is created
    updated_ad = models.DateTimeField(auto_now=True) 
    tiktok = models.CharField(_("tiktok"), max_length=200, blank=True,null=True)
    youtube = models.CharField(_("youtube"), max_length=200, blank=True,null=True)
    facebook = models.CharField(_("facebook"), max_length=200, blank=True,null=True)
    instagram = models.CharField(_("instagram"), max_length=200, blank=True,null=True)
    linkedin = models.CharField(_("linkedin"), max_length=200, blank=True,null=True)
    twitter = models.CharField(_("twitter"), max_length=200, blank=True,null=True)

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
    tech = models.TextField()
    expertise = models.TextField()
    experience_years = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    agreement = models.BooleanField(default=False, help_text="Check if the user agrees to the terms and conditions")
    provider =models.ForeignKey(Partner,on_delete=models.CASCADE,related_name='instructors')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} "
    
class Category(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)  # Relasi dengan pengguna
    name = models.CharField(max_length=250)
    slug = models.SlugField(unique=True, blank=True, null=True)  # Kolom slug yang unik

    def save(self, *args, **kwargs):
        # Jika slug belum ada, buat slug dari nama kategori
        if not self.slug:
            self.slug = slugify(self.name)

            # Pastikan slug unik
            original_slug = self.slug
            counter = 1
            while Category.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1

        super().save(*args, **kwargs)  # Panggil metode save dari superclass

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
    choice_language = [
        ('ab', 'Abkhazian'), ('aa', 'Afar'), ('af', 'Afrikaans'), ('sq', 'Albanian'), ('am', 'Amharic'),
        ('ar', 'Arabic'), ('hy', 'Armenian'), ('as', 'Assamese'), ('av', 'Avaric'), ('ae', 'Avestan'),
        ('ay', 'Aymara'), ('az', 'Azerbaijani'), ('bm', 'Bambara'), ('ba', 'Bashkir'), ('eu', 'Basque'),
        ('be', 'Belarusian'), ('bn', 'Bengali'), ('bh', 'Bihari'), ('bi', 'Bislama'), ('bs', 'Bosnian'),
        ('br', 'Breton'), ('bg', 'Bulgarian'), ('my', 'Burmese'), ('ca', 'Catalan'), ('ch', 'Chamorro'),
        ('ce', 'Chechen'), ('ny', 'Chichewa'), ('zh', 'Chinese'), ('cu', 'Church Slavic'), ('cv', 'Chuvash'),
        ('kw', 'Cornish'), ('co', 'Corsican'), ('cr', 'Cree'), ('hr', 'Croatian'), ('cs', 'Czech'),
        ('da', 'Danish'), ('dv', 'Divehi'), ('nl', 'Dutch'), ('dz', 'Dzongkha'), ('en', 'English'),
        ('eo', 'Esperanto'), ('et', 'Estonian'), ('ee', 'Ewe'), ('fo', 'Faroese'), ('fj', 'Fijian'),
        ('fi', 'Finnish'), ('fr', 'French'), ('ff', 'Fulah'), ('de', 'German'), ('ga', 'Irish'),
        ('gl', 'Galician'), ('gn', 'Guarani'), ('gu', 'Gujarati'), ('ht', 'Haitian Creole'), ('ha', 'Hausa'),
        ('he', 'Hebrew'), ('hi', 'Hindi'), ('ho', 'Hiri Motu'), ('hu', 'Hungarian'), ('is', 'Icelandic'),
        ('id', 'Indonesian'), ('ia', 'Interlingua'), ('ie', 'Interlingue'), ('iu', 'Inuktitut'), ('it', 'Italian'),
        ('ja', 'Japanese'), ('jw', 'Javanese'), ('kn', 'Kannada'), ('kr', 'Kanuri'), ('ks', 'Kashmiri'),
        ('km', 'Khmer'), ('ki', 'Kikuyu'), ('rw', 'Kinyarwanda'), ('ky', 'Kyrgyz'), ('ko', 'Korean'),
        ('la', 'Latin'), ('lv', 'Latvian'), ('lt', 'Lithuanian'), ('lb', 'Luxembourgish'), ('mk', 'Macedonian'),
        ('ml', 'Malayalam'), ('mr', 'Marathi'), ('my', 'Mongolian'), ('ne', 'Nepali'), ('no', 'Norwegian'),
        ('oc', 'Occitan'), ('or', 'Odia'), ('om', 'Oromo'), ('ps', 'Pashto'), ('fa', 'Persian'),
        ('pl', 'Polish'), ('pt', 'Portuguese'), ('pa', 'Punjabi'), ('qu', 'Quechua'), ('ro', 'Romanian'),
        ('rm', 'Romansh'), ('ru', 'Russian'), ('sr', 'Serbian'), ('si', 'Sinhala'), ('sk', 'Slovak'),
        ('sl', 'Slovenian'), ('es', 'Spanish'), ('su', 'Sundanese'), ('sw', 'Swahili'), ('sv', 'Swedish'),
        ('tl', 'Tagalog'), ('tg', 'Tajik'), ('ta', 'Tamil'), ('te', 'Telugu'), ('th', 'Thai'),
        ('tr', 'Turkish'), ('uk', 'Ukrainian'), ('ur', 'Urdu'), ('uz', 'Uzbek'), ('vi', 'Vietnamese'),
        ('cy', 'Welsh'), ('xh', 'Xhosa'), ('yi', 'Yiddish'), ('zu', 'Zulu'),
    ]
    PAYMENT_MODEL_CHOICES = [
        ('buy_first', 'Buy first, then enroll'),
        ('pay_for_exam', 'Enroll first, pay at exam'),
        ('pay_for_certificate', 'Enroll & take exam first, pay at certificate claim'),
        ('free', 'Free'),
    ]

    course_name = models.CharField(max_length=250)
    course_number = models.CharField(max_length=250, blank=True)
    course_run = models.CharField(max_length=250, blank=True)
    slug = models.CharField(max_length=250, blank=True)
    org_partner = models.ForeignKey('Partner', on_delete=models.CASCADE, related_name="courses")
    instructor = models.ForeignKey('Instructor', on_delete=models.CASCADE, related_name="courses", null=True)
    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name="category_courses")
    level = models.CharField(max_length=10, choices=[('basic', 'Basic'), ('middle', 'Middle'), ('advanced', 'Advanced')], default='basic', null=True, blank=True)
    status_course = models.ForeignKey('CourseStatus', on_delete=models.CASCADE, related_name="courses")
    created_at = models.DateTimeField(auto_now_add=True)
    edited_on = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='courses/', blank=True, null=True)
    link_video = models.URLField(blank=True, null=True)
    description = models.TextField()
    sort_description = models.CharField(max_length=150, null=True, blank=True)
    hour = models.CharField(max_length=2, null=True, blank=True)
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    language = models.CharField(max_length=2, choices=choice_language, default='id')
    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)
    start_enrol = models.DateField(null=True)
    end_enrol = models.DateField(null=True)
    payment_model = models.CharField(max_length=20, choices=PAYMENT_MODEL_CHOICES, default='buy_first')
    view_count = models.PositiveIntegerField(default=0)  # total view

    class Meta:
        indexes = [
            models.Index(fields=['status_course', 'end_enrol']),
            models.Index(fields=['category', 'language', 'level']),
            models.Index(fields=['org_partner']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.pk and not self.status_course:
            self.status_course = CourseStatus.objects.create(
                status='draft',
                manual_message="Kursus dibuat sebagai Draft."
            )
        self.delete_old_image()
        super().save(*args, **kwargs)

    def get_course_price(self, partner=None, price_type=None):
        course_price = self.prices.filter(partner=partner if partner else self.org_partner)

        if price_type:
            course_price = course_price.filter(price_type=price_type)
        else:
            try:
                tipe_harga_default = PricingType.objects.get(name=self.payment_model)
                course_price = course_price.filter(price_type=tipe_harga_default)
            except PricingType.DoesNotExist:
                return None

        return course_price.first()


    
    
    logger = logging.getLogger(__name__)

    def enroll_user(self, user, partner=None, price_type=None):
        logger.debug(f"Enrolling user {user.email} (ID: {user.id}) for course {self.course_name} (ID: {self.id}) with payment_model {self.payment_model}")

        # Cek apakah pendaftaran masih terbuka
        if not self.is_enrollment_open():
            logger.error(f"Enrollment closed for course {self.course_name}")
            return {"status": "error", "message": "Pendaftaran untuk kursus ini telah ditutup."}

        # Pemeriksaan lisensi untuk semua pengguna yang terkait lisensi
        licenses = user.licenses.all()
        if licenses.exists():
            today = timezone.now().date()
            active_license = user.licenses.filter(
                start_date__lte=today,
                expiry_date__gte=today,
                status=True
            )
            logger.info(f"License check for user {user.email} in course {self.course_name}: {active_license.values('name', 'start_date', 'expiry_date', 'status')}")
            if not active_license.exists():
                logger.error(f"No active license found for user {user.email} in course {self.course_name}")
                return {"status": "error", "message": "Lisensi Anda sudah tidak aktif atau tidak valid. Silakan hubungi admin untuk perpanjangan."}

        # Logika untuk kursus gratis
        if self.payment_model == 'free':
            enrollment, created = Enrollment.objects.get_or_create(user=user, course=self)
            if created:
                logger.info(f"User {user.email} enrolled in free course {self.course_name}")
                return {"status": "success", "message": "Berhasil mendaftar ke kursus ini secara gratis."}
            logger.info(f"User {user.email} already enrolled in free course {self.course_name}")
            return {"status": "info", "message": "Anda sudah terdaftar di kursus ini."}

        # Dapatkan harga kursus (untuk non-free dan non-subscription)
        course_price = self.get_course_price(partner, price_type)
        if not course_price and self.payment_model != 'subscription':
            logger.error(f"No course price found for course {self.course_name}, partner {partner}, price_type {price_type}")
            return {"status": "error", "message": "Harga kursus tidak ditemukan untuk mitra atau tipe harga ini."}

        if self.payment_model == 'buy_first':
            payment = Payment.objects.filter(
                user=user, course=self, status='completed', payment_model='buy_first'
            ).first()
            if not payment:
                logger.error(f"No completed payment found for user {user.email} in course {self.course_name}")
                return {"status": "error", "message": "Pembayaran diperlukan sebelum mendaftar ke kursus ini."}
            enrollment, created = Enrollment.objects.get_or_create(user=user, course=self, payment=payment)
            if created:
                logger.info(f"User {user.email} enrolled in paid course {self.course_name} with payment ID {payment.id}")
                return {"status": "success", "message": "Berhasil mendaftar ke kursus ini."}
            logger.info(f"User {user.email} already enrolled in paid course {self.course_name}")
            return {"status": "info", "message": "Anda sudah terdaftar di kursus ini."}

        else:  # pay_for_exam, pay_for_certificate, atau subscription
            enrollment, created = Enrollment.objects.get_or_create(user=user, course=self)
            if created:
                logger.info(f"User {user.email} enrolled in course {self.course_name} with model {self.payment_model}")
                return {"status": "success", "message": "Berhasil mendaftar ke kursus ini."}
            logger.info(f"User {user.email} already enrolled in course {self.course_name}")
            return {"status": "info", "message": "Anda sudah terdaftar di kursus ini."}
    
    def can_access_assessment(self, user, partner=None, price_type=None):
        enrollment = Enrollment.objects.filter(user=user, course=self).first()
        if not enrollment:
            return {"status": "error", "message": "Anda belum terdaftar di kursus ini."}

        course_price = self.get_course_price(partner, price_type)
        if not course_price:
            return {"status": "error", "message": "Harga kursus tidak ditemukan untuk mitra atau tipe harga ini."}

        if self.payment_model in ['free', 'buy_first', 'pay_for_certificate']:
            return {"status": "success", "message": "Anda dapat mengakses ujian."}

        elif self.payment_model == 'pay_for_exam':
            payment = Payment.objects.filter(
                user=user, course=self, status='completed', payment_model='pay_for_exam'
            ).first()
            if not payment:
                return {"status": "error", "message": "Pembayaran diperlukan untuk mengakses ujian."}
            enrollment.payment = payment
            enrollment.save()
            return {"status": "success", "message": "Anda dapat mengakses ujian."}

    def can_claim_certificate(self, user, partner=None, price_type=None):
        enrollment = Enrollment.objects.filter(user=user, course=self).first()
        if not enrollment:
            return {"status": "error", "message": "Anda belum terdaftar di kursus ini."}

        progress = CourseProgress.objects.filter(user=user, course=self).first()
        if not progress or not progress.grade:
            return {"status": "error", "message": "Anda belum lulus kursus ini."}

        if enrollment.certificate_issued:
            return {"status": "info", "message": "Sertifikat sudah diterbitkan."}

        course_price = self.get_course_price(partner, price_type)
        if not course_price:
            return {"status": "error", "message": "Harga kursus tidak ditemukan untuk mitra atau tipe harga ini."}

        if self.payment_model in ['free', 'buy_first', 'pay_for_exam']:
            enrollment.certificate_issued = True
            enrollment.save()
            return {"status": "success", "message": "Sertifikat berhasil diterbitkan."}

        elif self.payment_model == 'pay_for_certificate':
            payment = Payment.objects.filter(
                user=user, course=self, status='completed', payment_model='pay_for_certificate'
            ).first()
            if not payment:
                return {"status": "error", "message": "Pembayaran diperlukan untuk mengklaim sertifikat."}
            enrollment.payment = payment
            enrollment.certificate_issued = True
            enrollment.save()
            return {"status": "success", "message": "Sertifikat berhasil diterbitkan."}

    def change_status(self, new_status, changed_by, message=None):
        try:
            status = CourseStatus.objects.get(status=new_status)
        except CourseStatus.DoesNotExist:
            raise ValueError(f"Status {new_status} tidak ditemukan di CourseStatus")

        if self.status_course == status:
            if message and message != self.status_course.manual_message:
                self.status_course.manual_message = message
                self.status_course.save()
            return

        self.status_course = status
        if message:
            self.status_course.manual_message = message
        self.status_course.save()
        self.save()

        CourseStatusHistory.objects.create(
            course=self,
            status=new_status,
            manual_message=message,
            changed_by=changed_by
        )

    def __str__(self):
        return self.course_name

    def delete_old_image(self):
        if self.pk:
            old_image = Course.objects.filter(pk=self.pk).values_list('image', flat=True).first()
            if old_image and old_image != self.image.name and default_storage.exists(old_image):
                default_storage.delete(old_image)

    def is_enrollment_open(self):
        today = date.today()
        return self.start_enrol <= today <= self.end_enrol if self.start_enrol and self.end_enrol else False

    def move_to_curation(self, message=None, user=None):
        if self.status_course.status != 'draft':
            raise ValidationError('Kursus tidak dalam tahap yang sesuai untuk kurasi.')
        self.status_course.status = 'curation'
        if message:
            self.status_course.manual_message = message
        self.status_course.save()
        CourseStatusHistory.objects.create(
            course=self, status=self.status_course.status, manual_message=message, changed_by=user
        )
        return {"status": "info", "message": "Kursus sedang dalam kurasi.", "manual_message": self.status_course.manual_message}

    def publish_course(self, message=None, user=None):
        if self.status_course.status != 'curation':
            raise ValidationError('Kursus tidak dalam tahap yang sesuai untuk dipublikasikan.')
        self.status_course.status = 'published'
        if message:
            self.status_course.manual_message = message
        self.status_course.save()
        CourseStatusHistory.objects.create(
            course=self, status=self.status_course.status, manual_message=message, changed_by=user
        )
        return {"status": "success", "message": "Kursus berhasil dipublikasikan.", "manual_message": self.status_course.manual_message}

    def archive_course(self, message=None, user=None):
        if self.status_course.status != 'published':
            raise ValidationError('Kursus tidak dapat diarsipkan sebelum dipublikasikan.')
        self.status_course.status = 'archived'
        if message:
            self.status_course.manual_message = message
        self.status_course.save()
        CourseStatusHistory.objects.create(
            course=self, status=self.status_course.status, manual_message=message, changed_by=user
        )
        return {"status": "info", "message": "Kursus telah diarsipkan.", "manual_message": self.status_course.manual_message}

    @property
    def average_rating(self):
        ratings = self.ratings.all()
        if ratings.exists():
            return round(sum(r.rating for r in ratings) / ratings.count(), 1)
        return 0

    @property
    def total_reviews(self):
        return self.ratings.count()

    def has_been_rated_by(self, user):
        return self.ratings.filter(user=user).exists()

class CourseViewLog(models.Model):
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='view_logs')
    date = models.DateField(default=timezone.now)
    count = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('course', 'date')

class CourseViewIP(models.Model):
    course = models.ForeignKey("Course", on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField()
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('course', 'ip_address')



class UserActivityLog(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=100)  # ex: "view_course", "login", etc.
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user} - {self.activity_type} - {self.timestamp}'
            
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
    certificate_issued = models.BooleanField(default=False)
    payment = models.ForeignKey(
        'payments.Payment', on_delete=models.SET_NULL, null=True, blank=True, related_name='enrollments'
    )

    def __str__(self):
        return f"{self.user.username} enrolled in {self.course.course_name}"

    class Meta:
        unique_together = ('user', 'course')

class CourseRating(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='ratings')
    rating = models.PositiveSmallIntegerField(choices=[(i, f"{i} ⭐") for i in range(1, 6)])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'course')

    def __str__(self):
        return f"{self.user.username} rated {self.course.course_name} - {self.rating}⭐"


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
    order = models.PositiveIntegerField(default=0)  # Field untuk menyimpan urutan

   
    def __str__(self):
        return self.title

    class Meta:
        #enforcing that there can not be two categories under a parent with same slug
        
        # __str__ method elaborated later in post.  use __unicode__ in place of
        ordering = ['order']
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


class MicroCredentialReview(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="microcredential_reviews")
    microcredential = models.ForeignKey(MicroCredential, on_delete=models.CASCADE, related_name="reviews")
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)], default=1)  # Rating dari 1 hingga 5
    review_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'microcredential')  # Pastikan setiap user hanya bisa memberi 1 review per microcredential

    def __str__(self):
        return f"Review by {self.user} for {self.microcredential} - Rating: {self.rating}"
    
class MicroCredentialEnrollment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="microcredential_enrollments")
    microcredential = models.ForeignKey('MicroCredential', on_delete=models.CASCADE, related_name="enrollments")
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'microcredential')  # Pastikan pengguna hanya terdaftar sekali per microcredential

    def __str__(self):
        return f"{self.user.username} enrolled in {self.microcredential.title}"
    
class MicroCredentialComment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField(blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    microcredential = models.ForeignKey('MicroCredential', on_delete=models.CASCADE)
    likes = models.IntegerField(default=0)
    dislikes = models.IntegerField(default=0)
    parent = models.ForeignKey("self", null=True, blank=True, related_name='replies', on_delete=models.CASCADE)

    class Meta:
        indexes = [models.Index(fields=['microcredential'])]

    def __str__(self):
        return f'Comment by {self.user.username} on {self.microcredential.title} at {self.created_at}'

    def is_spam(self):
        """
        Pengecekan untuk spam. Menggunakan interval waktu antara komentar.
        """
        last_comment_time = MicroCredentialComment.objects.filter(user=self.user).order_by('-created_at').first()
        if last_comment_time:
            time_difference = timezone.now() - last_comment_time.created_at
            if time_difference < timedelta(minutes=1):  # Jika komentar sebelumnya dibuat kurang dari 1 menit
                return True
        return False

    def contains_blacklisted_keywords(self):
        """
        Memeriksa apakah komentar mengandung kata-kata yang diblacklist.
        """
        blacklisted_keywords = BlacklistedKeyword.objects.values_list('keyword', flat=True)
        for keyword in blacklisted_keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', self.content.lower()):
                return True
        return False

    def get_replies(self):
        """
        Mengambil semua balasan (replies) dari komentar ini, diurutkan berdasarkan waktu pembuatan.
        """
        return self.replies.all().order_by('created_at')  # Mengambil semua balasan dari komentar ini

class MicroClaim(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)  
    microcredential = models.ForeignKey(MicroCredential, on_delete=models.CASCADE)
    claim_date = models.DateTimeField(auto_now_add=True)  
    certificate_id = models.CharField(max_length=255, unique=True)  # e.g., CERT-1-4
    certificate_uuid = models.UUIDField(unique=True, default=uuid.uuid4)  # untuk QR code
    verified = models.BooleanField(default=False)
    issued_at = models.DateTimeField(default=timezone.now)  # ⬅️ Tambahkan ini

    def verify_claim(self):
        self.verified = True
        self.save()

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.microcredential.title}"
    
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
        """
        Hitung skor final berdasarkan peer reviews untuk submisi ini.
        """
        course = self.submission.askora.assessment.section.courses  # Perbaikan: courses bukan course
        total_participants = (
            Enrollment.objects
            .filter(course=course)
            .aggregate(total=Count("user"))
            .get("total", 0)
        )

        peer_reviews = self.submission.peer_reviews.all()
        peer_review_count = peer_reviews.count()

        # ⚙️ Tentukan minimal peer review berdasarkan jumlah peserta
        if total_participants <= 1:
            # ⛳ Kasus hanya satu peserta → langsung kasih nilai otomatis
            avg_peer_score = Decimal('0')
        elif total_participants == 2:
            # 🤝 Cukup 1 peer review
            if peer_review_count < 1:
                self.final_score = None
                self.save()
                return
        else:
            # 👥 Untuk 3 peserta atau lebih, butuh minimal 3 review
            if peer_review_count < 3:
                self.final_score = None
                self.save()
                return

        # ✅ Hitung rata-rata skor review jika ada
        if peer_review_count > 0:
            total_score = sum(
                Decimal(review.score) * Decimal(review.weight or 1)
                for review in peer_reviews
            )
            avg_peer_score = total_score / Decimal(peer_review_count)
        else:
            avg_peer_score = Decimal('0')

        # ⚖️ Bobot skor: 50% jawaban peserta, 50%ied review teman
        participant_score = Decimal('5')  # nilai otomatis, bisa dinamis
        final_score = (participant_score * Decimal('0.5')) + (avg_peer_score * Decimal('0.5'))

        self.final_score = final_score
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


#untuk analitik
class CourseSessionLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE)

    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

    duration_seconds = models.PositiveIntegerField(default=0, help_text="Durasi belajar dalam detik.")

    user_agent = models.CharField(max_length=255, blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    location_country = models.CharField(max_length=100, blank=True, null=True)  # Tambahan
    location_city = models.CharField(max_length=100, blank=True, null=True)    # Tambahan

    def save(self, *args, **kwargs):
        if self.started_at and self.ended_at:
            self.duration_seconds = int((self.ended_at - self.started_at).total_seconds())
        super().save(*args, **kwargs)

    def __str__(self):
        durasi = self.duration_seconds
        menit = durasi // 60
        return f"{self.user.username} - {self.course.course_name} - {menit} menit"

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
    parent=models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE,related_name="children")

    class Meta:
        indexes = [
            models.Index(fields=['material']),
        ]
    
    def __str__(self):
        return f'Comment by {self.user.username} on {self.created_at}'
    def contains_blacklisted_keywords(self):
        blacklisted_keywords = BlacklistedKeyword.objects.values_list('keyword', flat=True)
        for keyword in blacklisted_keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', self.content.lower()):
                return True
        return False
    
class CommentReaction(models.Model):
    REACTION_LIKE = 'LIKE'
    REACTION_DISLIKE = 'DISLIKE'
    REACTION_CHOICES = [
        (REACTION_LIKE, 'Like'),
        (REACTION_DISLIKE, 'Dislike'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='comment_reactions')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='reactions')
    reaction_type = models.CharField(max_length=10, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'comment']  # Satu pengguna, satu reaksi per komentar
        indexes = [
            models.Index(fields=['comment', 'user']),
        ]

    def __str__(self):
        return f"{self.user.username} {self.reaction_type} on Comment {self.comment.id}"    

class CourseComment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField(blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    course = models.ForeignKey('Course', on_delete=models.CASCADE)
    likes = models.IntegerField(default=0)
    dislikes = models.IntegerField(default=0)
    parent = models.ForeignKey("self", null=True, blank=True, related_name='replies', on_delete=models.CASCADE)

    class Meta:
        indexes = [models.Index(fields=['course'])]

    def __str__(self):
        return f'Comment by {self.user.username} on {self.created_at}'

    def is_spam(self):
        last_comment_time = CourseComment.objects.filter(user=self.user).order_by('-created_at').first()
        if last_comment_time:
            time_difference = timezone.now() - last_comment_time.created_at
            if time_difference < timedelta(minutes=1):
                return True
        return False

    def contains_blacklisted_keywords(self):
        blacklisted_keywords = BlacklistedKeyword.objects.values_list('keyword', flat=True)
        for keyword in blacklisted_keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', self.content.lower()):
                return True
        return False

    def get_replies(self):
        return self.replies.all().order_by('created_at')  # Mengambil semua balasan dari komentar ini

    




class SosPost(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    deleted = models.BooleanField(default=False)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')

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
        if self.retweet:  # Pastikan ada field retweet jika digunakan
            return None
        retweet_content = f"Retweeted: {self.content}"
        return SosPost.objects.create(
            user=user,
            content=retweet_content[:150],
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
    def __str__(self):
        return f'#{self.name}'

class Like(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    post = models.ForeignKey(SosPost, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')  # Memastikan kombinasi user dan post unik







class Certificate(models.Model):
    certificate_id = models.UUIDField(unique=True, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="certificates")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="certificates")
    issue_date = models.DateField()
    total_score = models.DecimalField(max_digits=5, decimal_places=2)
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Certificate {self.certificate_id} for {self.user.username} - {self.course.course_name}"

class SearchHistory(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="search_history")
    keyword = models.CharField(max_length=200)
    search_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - {self.keyword}"

    class Meta:
        ordering = ['-search_date']


class LastAccessCourse(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    material = models.ForeignKey(Material, null=True, blank=True, on_delete=models.SET_NULL)
    assessment = models.ForeignKey(Assessment, null=True, blank=True, on_delete=models.SET_NULL)
    last_viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'course')

class LTIExternalTool1(models.Model):
    assessment = models.OneToOneField('Assessment', on_delete=models.CASCADE, related_name='lti_tool')
    tool_name = models.CharField(max_length=255)
    launch_url = models.URLField(help_text="LTI launch URL dari provider.")
    tool_url = models.URLField(default="https://example.com")
    consumer_key = models.CharField(max_length=255, help_text="Consumer key (diberikan oleh provider).")
    shared_secret = models.CharField(max_length=255, help_text="Shared secret (diberikan oleh provider atau dibuat otomatis).")
    custom_parameters = models.TextField(blank=True, null=True, help_text="Custom parameters (format: key=value, satu per baris).")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tool_name} ({self.assessment})"
    
class LTIResult(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    assessment = models.ForeignKey('Assessment', on_delete=models.CASCADE)
    result_sourcedid = models.TextField()
    outcome_service_url = models.URLField()
    consumer_key = models.CharField(max_length=255)

    score = models.FloatField(null=True, blank=True)  # nilai 0.0 - 1.0
    last_sent_at = models.DateTimeField(null=True, blank=True)  # kapan nilai terakhir dikirim
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'assessment')

    def __str__(self):
        return f"LTIResult({self.user}, {self.assessment}, score={self.score})"