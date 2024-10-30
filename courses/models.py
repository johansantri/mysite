from django.db import models
from partner.models import Partner
from django.contrib.auth.models import User
import datetime
import os



    
class Category (models.Model):
    category_name = models.CharField(max_length=200,blank=True) 
    category_slug = models.CharField(max_length=200,blank=True)                 
  
   

    def __str__(self):
        return f"{self.category_name} "

Choi = (
    ('basic','basic'),
    ('medium','medium'),
    ('advanced','advanced'),
)

St = (
    ('draft','draft'),
    ('qurations','qurations'),
    ('publish','publish'),
    ('pending','pending'),
)

Tc = (
    ('self','self-paced'),
    ('instructor','instructor-paced'),
)


def filepath(request, filename):
    old_filename = filename
    timeNow = datetime.datetime.now().strftime('%Y%m%d%H:%M:%S')
    filename = "%s%s" % (timeNow, old_filename)
    return os.path.join('course/', filename)



def current_year():
    return datetime.date.today().year

class Course (models.Model):
    course_name = models.CharField(max_length=250)
    course_number = models.CharField(max_length=250, blank=True)
    course_run = models.CharField(max_length=250, blank=True)
    slug = models.CharField(max_length=250, blank=True)
    
    category = models.ForeignKey(Category, on_delete=models.CASCADE)       
    level = models.CharField(max_length=10, choices=Choi, default='basic', null=True, blank=True)
    status_course = models.CharField(max_length=10, choices=St, default='draft',blank=True)          
    org_partner = models.OneToOneField(Partner, on_delete=models.CASCADE)    
    author=models.ForeignKey(User, on_delete=models.CASCADE) 

    def __str__(self):
        return f"{self.course_name} {self.status_course}"
    

# Create your models here.
class Instructor (models.Model):
    name = models.ForeignKey(User, on_delete=models.CASCADE)              
    org = models.ForeignKey(Partner, on_delete=models.CASCADE)    
    mycourse = models.ForeignKey(Course, on_delete=models.CASCADE)  
   

    def __str__(self):
        return f"{self.name} - {self.org} - {self.mycourse}"
