from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.utils import timezone

CustomUser = get_user_model()

class Payment(models.Model):
    PAYMENT_MODEL_CHOICES = [
        ('buy_first', 'Buy first, then enroll'),
        ('pay_for_exam', 'Enroll first, pay at exam'),
        ('pay_for_certificate', 'Enroll & take exam first, pay at certificate claim'),
        ('free', 'Free'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('expired', 'Expired'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='payments')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='payments')
    payment_model = models.CharField(max_length=30, choices=PAYMENT_MODEL_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=10, default='IDR')
    transaction_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    
    # Metode/gateway
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    payment_gateway = models.CharField(max_length=50, blank=True, null=True)

    # Relasi ke CoursePrice (boleh kosong)
    course_price = models.ForeignKey('courses.CoursePrice', on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')

    # Snapshot harga pada saat transaksi
    snapshot_price = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), verbose_name="Snapshot Normal Price")
    snapshot_discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Snapshot Discount")
    snapshot_tax = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Snapshot Tax (%)")
    snapshot_ppn = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Snapshot PPN Value")
    snapshot_user_payment = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), verbose_name="Snapshot User Payment")
    snapshot_partner_earning = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), verbose_name="Snapshot Partner Earning")
    snapshot_ice_earning = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), verbose_name="Snapshot ICE Earning")

    # Opsional
    notes = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('user', 'course', 'payment_model')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.course.course_name} - {self.payment_model} - {self.status}"

    def apply_course_price_snapshot(self):
        """
        Salin semua informasi harga dari CoursePrice saat ini ke snapshot.
        """
        if self.course_price:
            cp = self.course_price
            self.snapshot_price = cp.normal_price
            self.snapshot_discount = cp.discount_amount
            self.snapshot_tax = cp.tax
            self.snapshot_ppn = cp.ppn
            self.snapshot_user_payment = cp.user_payment
            self.snapshot_partner_earning = cp.partner_earning
            self.snapshot_ice_earning = cp.ice_earning

            # Set amount ke harga aktual yang dibayar user
            self.amount = cp.user_payment

    def save(self, *args, **kwargs):
        if self.course_price:
            self.apply_course_price_snapshot()
        # Auto isi paid_at jika status jadi completed
        if self.status == 'completed' and not self.paid_at:
            self.paid_at = timezone.now()
        super().save(*args, **kwargs)

class CartItem(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'course')

    def __str__(self):
        return f"{self.user} - {self.course}"
    

class Transaction(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    courses = models.ManyToManyField('courses.Course')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('paid', 'Paid')])
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)