from django.db import models
from django.contrib.auth.models import User
import uuid
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
    e_mail = models.ForeignKey(User,on_delete=models.CASCADE)
    phone = models.CharField(max_length=50)
    address = models.TextField(max_length=50)
    tax = models.CharField(max_length=50)
    status = models.CharField(max_length=50)
    checks = models.CharField(max_length=50)
    logo = models.ImageField(upload_to=filepath,null=True, blank=True)
    join = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.partner_name}"
    
class Invitation(models.Model):
    email = models.EmailField(unique=True)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)  # Unique token for invitation link
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="invitations_sent")
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Invitation for {self.email}"