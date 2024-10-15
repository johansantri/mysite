from django.db import models
from partner.models import Partner
from django.contrib.auth.models import User
import datetime
import os

# Create your models here.



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
Lg = (
    ('en','english'),
    ('id','indonesia'),
)
Tc = (
    ('self','self-paced'),
    ('instructor','instructor-paced'),
)
Ct = (
    ('tecnologi','tecnologi'),
    ('law','law'),
    ('economic','economic'),
    ('social','social'),
    ('agriculture','agriculture'),
    ('mining','mining'),
    ('management','management'),
    ('program','program'),
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
    slug = models.CharField(max_length=250)
    topic = models.CharField(max_length=250)
    course_overview = models.TextField(null=True)
    category = models.CharField(max_length=50, choices=Ct,null=True)
    number_of_questions = models.IntegerField(null=True)
    time = models.IntegerField(help_text="durations of the quiz in minutes",null=True)
    required_score_to_pas = models.IntegerField("required score in %", null=True)
    level = models.CharField(max_length=10, choices=Choi, default='basic', null=True)
    status_course = models.CharField(max_length=10, choices=St, default='draft')
    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)
    start_enrol = models.DateField(null=True)
    end_enrol = models.DateField(null=True)
    effort = models.CharField(max_length=20, null=True)
    lang = models.CharField(max_length=30, choices=Lg, default='id')
    org_partner = models.ForeignKey(Partner, on_delete=models.CASCADE)
    type_course = models.CharField(max_length=10, choices=Tc, default='self')
    image_course = models.ImageField(upload_to=filepath,null=True)
    author=models.ForeignKey(User,on_delete=models.CASCADE)
    course_year=models.IntegerField(null=True, default=current_year)

    def __str__(self):
        return f"{self.course_name} {self.status_course}"
    

