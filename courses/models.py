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





class Partner(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE,related_name="partner_user")  # Add this line to associate partners with users
    name = models.ForeignKey(Universiti, on_delete=models.CASCADE,related_name="partner_univ")
    
    phone = models.CharField(max_length=50,null=True, blank=True)
    address = models.TextField(max_length=200,null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    tax = models.CharField(max_length=50,null=True, blank=True)
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