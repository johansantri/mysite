# models.py
from django.db import models
from django.contrib.auth.models import User

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
    
class Category(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Add this line to associate partners with users
    name = models.CharField(max_length=250)

    def __str__(self):
        return self.name

class Course(models.Model):
    course_name = models.CharField(max_length=250)
    course_number = models.CharField(max_length=250, blank=True)
    course_run = models.CharField(max_length=250, blank=True)
    slug = models.CharField(max_length=250, blank=True)
    org_partner = models.ForeignKey(Partner, on_delete=models.CASCADE,related_name="org_courses")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="category_courses")
    level = models.CharField(max_length=10, choices=[('basic', 'Basic'), ('advanced', 'Advanced')], default='basic', null=True, blank=True)
    status_course = models.CharField(max_length=10, choices=[('draft', 'Draft'), ('published', 'Published')], default='draft', blank=True)
   
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.course_name} ({self.status_course} - {self.org_partner} - {self.author} - {self.course_run})"
    

