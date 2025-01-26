from django.db import models

# Create your models here.
from django.contrib.auth.models import User,Universiti
from django.db.models.signals import post_save
class Profile(models.Model):
    user = models.OneToOneField(User,on_delete=models.CASCADE)
    follows = models.ManyToManyField("self", related_name="followed_by",symmetrical=False,blank=True)
    date_modified = models.DateTimeField(User,auto_now=True)
    def __str__(self):
        return self.user.username
    


def create_profile(sender, instance, created, **kwargs):
    if created:
        user_profile = Profile(user=instance)
        user_profile.save()
        user_profile.follows.set([instance.profile.id])
        user_profile.save()

    post_save.connect(create_profile,sender=User)