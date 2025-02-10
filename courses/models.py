# models.py
from django.db import models
from django.contrib.auth.models import User, Universiti
from autoslug import AutoSlugField
from django.utils.text import slugify
import os
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.db.models import Sum
from datetime import date
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone


class Partner(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE,related_name="partner_user")  # Add this line to associate partners with users
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
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="partner_author") 
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

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="instructors")
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
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Add this line to associate partners with users
    name = models.CharField(max_length=250)

    def __str__(self):
        return self.name



class Course(models.Model):
    course_name = models.CharField(max_length=250)
    #slug = AutoSlugField(populate_from='title', unique=True, null=False, editable=False)
    course_number = models.CharField(max_length=250, blank=True)
    course_run = models.CharField(max_length=250, blank=True)
    slug = models.CharField(max_length=250, blank=True)
    org_partner = models.ForeignKey(Partner, on_delete=models.CASCADE,related_name="courses")
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE,related_name="courses",null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="category_courses")
    level = models.CharField(max_length=10, choices=[('basic', 'Basic'),('middle', 'Middle'), ('advanced', 'Advanced')], default='basic', null=True, blank=True)
    status_course = models.CharField(max_length=10, choices=[('draft', 'draft'), ('published', 'published'),('curation', 'curation'),('archive', 'archive')], default='draft', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_on = models.DateTimeField(auto_now=True) 
    image = models.ImageField(upload_to='courses/', blank=True, null=True)
    link_video = models.URLField(blank=True, null=True) 
    description = models.TextField()
    sort_description = models.CharField(max_length=150, null=True,blank=True)
    hour = models.CharField(max_length=2,null=True,blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    language = models.CharField(max_length=10,choices=[('en', 'English'),('id', 'Indonesia'), ('fr', 'French'), ('de', 'German')], default='en')
    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)
    start_enrol = models.DateField(null=True)
    end_enrol = models.DateField(null=True)


    def __str__(self):

        return f"{self.course_name}"
    
    def delete_old_image(self):
        """
        Hapus gambar lama jika sudah diganti.
        """
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
    
    def create_rerun(self, course_run_input=None):
        today = timezone.now().date()  # Get today's date in a timezone-aware format

        # Check if a re-run exists for this course today
        existing_rerun = Course.objects.filter(
            course_name=self.course_name,  # Same course name
            course_run__startswith="Run",  # Check if it's a re-run
            created_at__date=today  # Check if it's the same day
        ).exists()

        if existing_rerun:
            raise ValidationError(f"A re-run for this course has already been created today.")

        # Allow the user to input `course_run` manually, if provided
        if course_run_input:
            new_course_run = course_run_input  # Use the user input for course_run
        else:
            # If no manual input, auto-generate course_run based on the last re-run
            if self.course_run:
                try:
                    run_number = int(self.course_run.split()[-1]) + 1  # Increment the last number
                except ValueError:
                    run_number = 2  # Default to "Run 2" if parsing fails
                new_course_run = f"Run {run_number}"
            else:
                new_course_run = "Run 2"

        # Keep the same `course_number` as the original course
        new_course_number = self.course_number  # Reuse the same course_number from the original course

        # Ensure course_number is unique (check if it already exists)
        while Course.objects.filter(course_number=new_course_number).exists():
            # If the course_number already exists, increment it
            new_course_number = f"{new_course_run}-{str(timezone.now().year)}-{str(timezone.now().month).zfill(2)}-{str(timezone.now().day).zfill(2)}"  # Unique identifier

        # Generate a new unique slug
        new_slug = f"{slugify(self.course_name)}-{new_course_run.lower().replace(' ', '-')}"
        
        # Create a new instance for the re-run course
        new_course = Course(
            course_name=self.course_name,
            course_run=new_course_run,
            course_number=new_course_number,  # Keep the same course_number as the original course
            slug=new_slug,
            org_partner=self.org_partner,
            instructor=self.instructor,  # Ensure instructor is copied
            category=self.category,
            level=self.level,
            status_course="draft",  # Start as draft
            image=self.image,  # Copy the image from the original course
            link_video=self.link_video,  # Copy the link_video from the original course
            description=self.description,  # Copy the description from the original course
            sort_description=self.sort_description,  # Copy sort_description from the original course
            hour=self.hour,  # Copy hour from the original course
            author=self.author,  # Copy the author (current user)
            language=self.language,  # Copy the language from the original course
            start_date=self.start_date + timedelta(days=30) if self.start_date else None,
            end_date=self.end_date + timedelta(days=30) if self.end_date else None,
            start_enrol=self.start_enrol + timedelta(days=30) if self.start_enrol else None,
            end_enrol=self.end_enrol + timedelta(days=30) if self.end_enrol else None,
        )

        # Save the new course instance
        new_course.save()

        # Copy CoursePrice related to the new course
        for course_price in self.prices.all():
            CoursePrice.objects.create(
                course=new_course,
                price_type=course_price.price_type,
                partner=course_price.partner,
                partner_price=course_price.partner_price,
                discount_percent=course_price.discount_percent,
                discount_amount=course_price.discount_amount,
                ice_share_rate=course_price.ice_share_rate,
                admin_fee=course_price.admin_fee,
                sub_total=course_price.sub_total,
                portal_price=course_price.portal_price,
                normal_price=course_price.normal_price,
                calculate_admin_price=course_price.calculate_admin_price,
                platform_fee=course_price.platform_fee,
                voucher=course_price.voucher,
                user_payment=course_price.user_payment,
                partner_earning=course_price.partner_earning,
                ice_earning=course_price.ice_earning
            )

        # Copy Section and Material related to the new course
        for section in self.sections.all():
            # Create the new section first
            new_section = Section.objects.create(
                parent=None,  # Initially, no parent
                title=section.title,
                slug=section.slug,
                courses=new_course
            )

            # Salin material dan assessments terkait untuk section baru
            for material in section.materials.all():
                Material.objects.create(
                    section=new_section,
                    title=material.title,
                    description=material.description,
                    created_at=material.created_at
                )

            for assessment in section.assessments.all():
                new_assessment = Assessment.objects.create(
                    name=assessment.name,
                    section=new_section,
                    weight=assessment.weight,
                    description=assessment.description,
                    flag=assessment.flag,
                    grade_range=assessment.grade_range,
                    created_at=assessment.created_at
                )

                for question in assessment.questions.all():
                    new_question = Question.objects.create(
                        assessment=new_assessment,
                        text=question.text,
                        created_at=question.created_at
                    )
                    
                    for choice in question.choices.all():
                        Choice.objects.create(
                            question=new_question,
                            text=choice.text,
                            is_correct=choice.is_correct
                        )

            # Handle child sections for the new section
            for child_section in section.children.all():
                # Create new child sections, and set the parent to the new section
                new_child_section = Section.objects.create(
                    parent=new_section,  # Set parent correctly for child
                    title=child_section.title,
                    slug=child_section.slug,
                    courses=new_course
                )

                # Copy materials and assessments for the child section
                for material in child_section.materials.all():
                    Material.objects.create(
                        section=new_child_section,
                        title=material.title,
                        description=material.description,
                        created_at=material.created_at
                    )

                for assessment in child_section.assessments.all():
                    new_assessment = Assessment.objects.create(
                        name=assessment.name,
                        section=new_child_section,
                        weight=assessment.weight,
                        description=assessment.description,
                        flag=assessment.flag,
                        grade_range=assessment.grade_range,
                        created_at=assessment.created_at
                    )

                    for question in assessment.questions.all():
                        new_question = Question.objects.create(
                            assessment=new_assessment,
                            text=question.text,
                            created_at=question.created_at
                        )
                        
                        for choice in question.choices.all():
                            Choice.objects.create(
                                question=new_question,
                                text=choice.text,
                                is_correct=choice.is_correct
                            )

        return new_course






    
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
    


class Enrollment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} enrolled in {self.course.course_name}"
    
    class Meta:
        unique_together = ('user', 'course')  # User hanya bisa mendaftar 1x ke tiap course

class TeamMember(models.Model):

    course = models.ForeignKey(Course, related_name='team_members', on_delete=models.CASCADE)

    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Change name to user

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

class Assessment(models.Model):
    name = models.CharField(max_length=255)
    section = models.ForeignKey(Section, related_name="assessments", on_delete=models.CASCADE)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Bobot untuk penilaian ini
    description = models.TextField(blank=True, null=True)
    flag = models.BooleanField(default=False)
    grade_range = models.ForeignKey(GradeRange, related_name="assessments", on_delete=models.SET_NULL, null=True, blank=True)  # Menghubungkan dengan rentang nilai
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} "
    def save(self, *args, **kwargs):
        # Hapus validasi bobot dari sini jika sudah dilakukan di views
        # if self.weight > 100:  # Removed because validation is in views
        #     raise ValueError("Total bobot untuk penilaian dalam section ini tidak boleh melebihi 100")
        
        super().save(*args, **kwargs)


class Question(models.Model):
    assessment = models.ForeignKey(Assessment, related_name="questions", on_delete=models.CASCADE)
    text = models.CharField(blank=True, null=True,max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(blank=True, null=True, max_length=200)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text



    
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