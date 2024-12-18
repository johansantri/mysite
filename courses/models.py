# models.py
from django.db import models
from django.contrib.auth.models import User
from autoslug import AutoSlugField


        
class Partner(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Add this line to associate partners with users
    name = models.CharField(max_length=250)
    abbreviation = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=50,null=True, blank=True)
    address = models.TextField(max_length=50,null=True, blank=True)
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
        return f"{self.name} - {self.user} - {self.updated_ad}"
    class Meta:
        indexes = [
            models.Index(fields=['user'])
    ]
    
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
    org_partner = models.ForeignKey(Partner, on_delete=models.CASCADE,related_name="org_courses")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="category_courses")
    level = models.CharField(max_length=10, choices=[('basic', 'Basic'),('middle', 'Middle'), ('advanced', 'Advanced')], default='basic', null=True, blank=True)
    status_course = models.CharField(max_length=10, choices=[('draft', 'draft'), ('published', 'published'),('curation', 'curation'),('archive', 'archive')], default='draft', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_on = models.DateTimeField(auto_now=True) 
    image = models.ImageField(upload_to='courses/images/', blank=True, null=True)
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
        return f"{self.course_name} ({self.status_course} - {self.org_partner} - {self.author} - {self.course_run})"
    

class Section(models.Model):
    parent = models.ForeignKey('self', related_name='children', on_delete=models.CASCADE, blank = True, null=True)
    title = models.CharField(max_length=100) 
    slug = AutoSlugField(populate_from='title', unique=True, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    courses=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='course_id')

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