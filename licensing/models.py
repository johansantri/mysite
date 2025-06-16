from django.db import models
import uuid
from django.contrib.auth import get_user_model
from django.utils import timezone
from authentication.models import Universiti
from django.conf import settings

User = get_user_model()

class License(models.Model):
    LICENSE_TYPE_CHOICES = [
        ('free', 'Gratis'),
        ('paid', 'Berbayar'),
        ('trial', 'Uji Coba'),
    ]
    SUBSCRIPTION_FREQUENCY_CHOICES = [
        ('monthly', 'Bulanan'),
        ('yearly', 'Tahunan'),
        ('once', 'Sekali'),
    ]
    
    users = models.ManyToManyField(User, related_name='licenses', verbose_name='Pengguna')
    name = models.CharField(max_length=255, verbose_name='Nama Lisensi')
    license_type = models.CharField(max_length=10, choices=LICENSE_TYPE_CHOICES, default='trial', verbose_name='Tipe Lisensi')
    start_date = models.DateField(default=timezone.now, verbose_name='Tanggal Mulai')
    expiry_date = models.DateField(verbose_name='Tanggal Berakhir')
    status = models.BooleanField(default=True, verbose_name='Status')
    description = models.TextField(blank=True, null=True, verbose_name='Deskripsi')
    university = models.ForeignKey(Universiti, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Universitas')
    max_users = models.PositiveIntegerField(default=20, verbose_name='Maksimum Pengguna')
    
    subscription_type = models.CharField(max_length=20, choices=LICENSE_TYPE_CHOICES, default='paid', verbose_name='Tipe Langganan')
    subscription_frequency = models.CharField(max_length=20, choices=SUBSCRIPTION_FREQUENCY_CHOICES, default='yearly', verbose_name='Frekuensi Langganan')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_licenses',
        verbose_name='Pemilik Lisensi'
    )
    def __str__(self):
        return f"{self.name}"
    
    class Meta:
        verbose_name = 'Lisensi'
        verbose_name_plural = 'Lisensi'
    
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
        return self.users.count() < self.max_users

    @property
    def remaining_slots(self):
        return self.max_users - self.users.count()

class Invitation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Menunggu'),
        ('accepted', 'Diterima'),
        ('expired', 'Kadaluarsa'),
    ]

    inviter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations', verbose_name='Pengundang')
    invitee_email = models.EmailField(verbose_name='Email Penerima')
    license = models.ForeignKey(License, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Lisensi Terkait')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name='Status')
    invitation_date = models.DateTimeField(auto_now_add=True, verbose_name='Tanggal Undangan')
    expiry_date = models.DateTimeField(default=timezone.now() + timezone.timedelta(days=7), verbose_name='Tanggal Kadaluarsa')
    token = models.CharField(max_length=255, blank=True, null=True, unique=True, verbose_name='Token')

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = str(uuid.uuid4())
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Undangan dari {self.inviter.username} ke {self.invitee_email}"
    
    def is_expired(self):
        return timezone.now() > self.expiry_date