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
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='licenses', verbose_name='User')
    name = models.CharField(max_length=255, verbose_name='License Name')  # Nama lisensi
    license_type = models.CharField(max_length=10, choices=LICENSE_TYPE_CHOICES, default='trial', verbose_name='License Type')
    start_date = models.DateField(default=timezone.now, verbose_name='Start Date')  # Tanggal mulai lisensi
    expiry_date = models.DateField(verbose_name='Expiry Date')  # Tanggal kadaluarsa lisensi
    status = models.BooleanField(default=True, verbose_name='Status')  # Status lisensi, apakah aktif atau tidak
    description = models.TextField(blank=True, null=True, verbose_name='Description')  # Deskripsi lisensi
    university = models.ForeignKey(Universiti, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='University')  # Relasi dengan Universitas (Opsional)
    
    # Additional fields for subscription
    subscription_type = models.CharField(
        max_length=20,
        choices=LICENSE_TYPE_CHOICES,
        default='paid',
        verbose_name='Subscription Type'
    )
    subscription_frequency = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_FREQUENCY_CHOICES,
        default='monthly',
        verbose_name='Subscription Frequency'
    )
    
    def __str__(self):
        return f"{self.name} ({self.user.username})"

    class Meta:
        verbose_name = 'License'
        verbose_name_plural = 'Licenses'

    def is_expired(self):
        """Menentukan apakah lisensi sudah kedaluwarsa."""
        return timezone.now().date() > self.expiry_date

    def is_approaching_expiry(self, days=7):
        """Menentukan apakah lisensi hampir kedaluwarsa dalam beberapa hari ke depan."""
        return self.expiry_date <= timezone.now().date() + timezone.timedelta(days=days)

    def save(self, *args, **kwargs):
        """Override untuk memeriksa apakah lisensi sudah kedaluwarsa dan menonaktifkan statusnya."""
        if self.is_expired():
            self.status = False  # Menonaktifkan status jika lisensi sudah kedaluwarsa
        super().save(*args, **kwargs)

    def extend_license(self):
        """Memperpanjang lisensi berdasarkan frekuensi langganan (bulanan atau tahunan)."""
        if self.subscription_frequency == 'monthly':
            self.expiry_date += timezone.timedelta(days=30)  # Menambah 30 hari untuk langganan bulanan
        elif self.subscription_frequency == 'yearly':
            self.expiry_date += timezone.timedelta(days=365)  # Menambah 365 hari untuk langganan tahunan
        self.save()


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
    token = models.CharField(max_length=255, blank=True, null=True, unique=True, verbose_name='Token')  # New field for token

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = str(uuid.uuid4())  # Generate a new token if not already present
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invite from {self.inviter.username} to {self.invitee_email}"

    def is_expired(self):
        """Check if invitation has expired."""
        return timezone.now() > self.expiry_date