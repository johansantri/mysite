from django.db import models
from django.contrib.auth.models import User
# Create your models here.
import datetime
import os

def filepath(request, filename):
    old_filename = filename
    timeNow = datetime.datetime.now().strftime('%Y%m%d%H:%M:%S')
    filename = "%s%s" % (timeNow, old_filename)
    return os.path.join('uploads/', filename)

class Partner(models.Model):
    partner_name = models.TextField(max_length=191)
    abbreviation = models.CharField(max_length=50)
    e_mail = models.OneToOneField(User,on_delete=models.CASCADE)
    phone = models.CharField(max_length=50)
    address = models.TextField(max_length=50)
    tax = models.CharField(max_length=50)
    status = models.CharField(max_length=50)
    checks = models.CharField(max_length=50)
    logo = models.ImageField(upload_to=filepath,null=True, blank=True)
    join = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.partner_name}"