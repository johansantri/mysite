# authentication/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save

class Universiti(models.Model):
    name = models.CharField(max_length=200, blank=True, null=True)
    slug = models.SlugField(unique=True)
    location = models.CharField(max_length=100, blank=True, null=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    
class CustomUser(AbstractUser):
    gen = {
        "male":"male",
        "female":"female",
    }
    edu = {
        "Basic":"Basic",
        "Secondary":"Secondary",
        "Higher":"Higher",
        "Diploma":"Diploma",
        "Bachelor's":"Bachelor",
        "Master":"Master",
        "Doctorate":"Doctorate",
    }
    email = models.EmailField(_("email address"), unique=True)  # Menambahkan unique=True
    phone = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=[('M', 'Male'), ('F', 'Female')], blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    birth = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    hobby = models.CharField(_("hobby"), max_length=150, blank=True)
    education = models.CharField(_("education"), max_length=10, choices=edu,blank=True)
    gender = models.CharField(_("gender"), max_length=8, choices=gen,blank=True)
    university = models.ForeignKey(Universiti, on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("university"))

    # Social Media Fields
    tiktok = models.CharField(_("tiktok"), max_length=200, blank=True)
    youtube = models.CharField(_("youtube"), max_length=200, blank=True)
    facebook = models.CharField(_("facebook"), max_length=200, blank=True)
    instagram = models.CharField(_("instagram"), max_length=200, blank=True)
    linkedin = models.CharField(_("linkedin"), max_length=200, blank=True)
    twitter = models.CharField(_("twitter"), max_length=200, blank=True)

    # Status Fields
    is_member = models.BooleanField(_("member status"), default=False, help_text=_("Designates whether the user can log into this admin member."))
    is_subscription = models.BooleanField(_("subscription status"), default=False, help_text=_("Designates whether the user can log into this admin subscription."))
    is_instructor = models.BooleanField(_("instructor status"), default=False, help_text=_("Designates whether the user can log into this admin instructor."))
    is_partner = models.BooleanField(_("partner status"), default=False, help_text=_("Designates whether the user can log into this admin partner."))
    is_audit = models.BooleanField(_("audit status"), default=False, help_text=_("Designates whether the user can log into this admin audit."))
    is_learner = models.BooleanField(_("learner status"), default=True, help_text=_("Designates whether the user can log into this admin learner."))
    is_note = models.BooleanField(_("note status"), default=False, help_text=_("Designates whether the user can log into this admin note."))

    # Authentication Fields
    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.username
class Profile(models.Model):
    user = models.OneToOneField(CustomUser,on_delete=models.CASCADE)
    follows = models.ManyToManyField("self", related_name="followed_by",symmetrical=False,blank=True)
    date_modified = models.DateTimeField(CustomUser,auto_now=True)
    def __str__(self):
        return self.user.username
    


def create_profile(sender, instance, created, **kwargs):
    if created:
        user_profile = Profile(user=instance)
        user_profile.save()
        user_profile.follows.set([instance.profile.id])
        user_profile.save()

    post_save.connect(create_profile,sender=CustomUser)