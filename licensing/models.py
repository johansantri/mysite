from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from authentication.models import CustomUser, Universiti

# Ambil model pengguna yang sudah didefinisikan sebelumnya
User = get_user_model()

class License(models.Model):
    LICENSE_TYPE_CHOICES = [
        ('free', 'Free'),
        ('paid', 'Paid'),
        ('trial', 'Trial'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='licenses', verbose_name='User')
    name = models.CharField(max_length=255, verbose_name='License Name')  # Nama lisensi
    license_type = models.CharField(max_length=10, choices=LICENSE_TYPE_CHOICES, default='trial', verbose_name='License Type')
    start_date = models.DateField(default=timezone.now, verbose_name='Start Date')  # Tanggal mulai lisensi
    expiry_date = models.DateField(verbose_name='Expiry Date')  # Tanggal kadaluarsa lisensi
    status = models.BooleanField(default=True, verbose_name='Status')  # Status lisensi, apakah aktif atau tidak
    description = models.TextField(blank=True, null=True, verbose_name='Description')  # Deskripsi lisensi
    university = models.ForeignKey(Universiti, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='University')  # Relasi dengan Universitas (Opsional)
    
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
            self.status = False  # Menonaktifkan status jika lisensi sudah kadaluarsa
        super().save(*args, **kwargs)

    def extend_license(self, days: int):
        """Memperpanjang lisensi dengan menambah jumlah hari ke tanggal kadaluarsa."""
        self.expiry_date += timezone.timedelta(days=days)
        self.save()
