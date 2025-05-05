from django.db import models
import uuid
from django.contrib.auth import get_user_model
from django.utils import timezone
from authentication.models import CustomUser, Universiti

User = get_user_model()

class License(models.Model):
    LICENSE_TYPE_CHOICES = [
        ('free', 'Free'),
        ('paid', 'Paid'),
        ('trial', 'Trial'),
    ]
    
    SUBSCRIPTION_FREQUENCY_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('once', 'One-time'),
    ]
    
    users = models.ManyToManyField(CustomUser, related_name='licenses', verbose_name='Users')  # Ubah ke ManyToManyField
    name = models.CharField(max_length=255, verbose_name='License Name')
    license_type = models.CharField(max_length=10, choices=LICENSE_TYPE_CHOICES, default='trial', verbose_name='License Type')
    start_date = models.DateField(default=timezone.now, verbose_name='Start Date')
    expiry_date = models.DateField(verbose_name='Expiry Date')
    status = models.BooleanField(default=True, verbose_name='Status')
    description = models.TextField(blank=True, null=True, verbose_name='Description')
    university = models.ForeignKey(Universiti, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='University')
    max_users = models.PositiveIntegerField(default=20, verbose_name='Maximum Users')  # Batas maksimum pengguna
    
    subscription_type = models.CharField(
        max_length=20,
        choices=LICENSE_TYPE_CHOICES,
        default='paid',
        verbose_name='Subscription Type'
    )
    subscription_frequency = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_FREQUENCY_CHOICES,
        default='yearly',  # Default ke yearly untuk PT A
        verbose_name='Subscription Frequency'
    )
    
    def __str__(self):
        return f"{self.name}"
    
    class Meta:
        verbose_name = 'License'
        verbose_name_plural = 'Licenses'
    
    def is_expired(self):
        return timezone.now().date() > self.expiry_date
    
    def is_approaching_expiry(self, days=7):
        return self.expiry_date <= timezone.now().date() + timezone.timedelta(days=days)
    
    def save(self, *args, **kwargs):
        if self.is_expired():
            self.status = False
        super().save(*args, **kwargs)
    
    def extend_license(self):
        if self.subscription_frequency == 'monthly':
            self.expiry_date += timezone.timedelta(days=30)
        elif self.subscription_frequency == 'yearly':
            self.expiry_date += timezone.timedelta(days=365)
        self.save()
    
    def can_add_user(self):
        """Cek apakah masih bisa menambahkan pengguna berdasarkan max_users."""
        return self.users.count() < self.max_users


class Invitation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('expired', 'Expired'),
    ]

    inviter = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_invitations', verbose_name='Inviter')
    invitee_email = models.EmailField(verbose_name='Invitee Email')
    license = models.ForeignKey('License', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Assigned License')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name='Status')
    invitation_date = models.DateTimeField(auto_now_add=True, verbose_name='Invitation Date')
    expiry_date = models.DateTimeField(default=timezone.now() + timezone.timedelta(days=7), verbose_name='Expiry Date')
    token = models.CharField(max_length=255, blank=True, null=True, unique=True, verbose_name='Token')

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = str(uuid.uuid4())
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Invite from {self.inviter.username} to {self.invitee_email}"
    
    def is_expired(self):
        return timezone.now() > self.expiry_date