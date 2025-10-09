from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.utils import timezone
from django.conf import settings

CustomUser = get_user_model()

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_MODEL_CHOICES = [
        ('free', 'Free'),
        ('buy_first', 'Buy First'),
        ('subscription', 'Subscription'),
        ('pay_for_exam', 'Pay for Exam'),
        ('pay_for_certificate', 'Pay for Certificate'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='User'
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Course'
    )
    payment_model = models.CharField(
        max_length=50,
        choices=PAYMENT_MODEL_CHOICES,
        default='buy_first',
        verbose_name='Payment Model'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Amount Paid (IDR)'
    )
    payment_date = models.DateTimeField(
        default=timezone.now,
        verbose_name='Payment Date'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Payment Status'
    )
    transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        help_text='Unique ID from payment gateway or transaction reference',
        verbose_name='Transaction ID'
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Additional Notes'
    )

    payment_method = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Payment Method'
    )
    payment_url = models.URLField(
        blank=True,
        null=True,
        verbose_name='Payment URL'
    )

    access_granted = models.BooleanField(default=False)
    access_granted_date = models.DateTimeField(null=True, blank=True)


    # Snapshot fields
    snapshot_price = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    snapshot_discount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    snapshot_tax = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    snapshot_ppn = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    snapshot_user_payment = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    snapshot_partner_earning = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    snapshot_ice_earning = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    snapshot_platform_fee = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    snapshot_voucher = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))

    # Tracking / meta info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    isp = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Course price snapshot object (optional serialization or JSON)
    course_price = models.JSONField(null=True, blank=True)
    
    # Link to Transaction
    linked_transaction = models.ForeignKey(
        'payments.Transaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name='Linked Transaction'
    )


    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated At')

    class Meta:
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['user', 'course', 'payment_model']),
            models.Index(fields=['status']),
        ]
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        return f"Payment {self.transaction_id or self.id} - {self.user} - {self.course.course_name} ({self.amount:,.2f} IDR)"

    def is_successful(self):
        return self.status == 'completed'

    def mark_completed(self, transaction_id=None):
        self.status = 'completed'
        if transaction_id:
            self.transaction_id = transaction_id
        self.payment_date = timezone.now()
        self.save()

    def mark_failed(self, transaction_id=None):
        self.status = 'failed'
        if transaction_id:
            self.transaction_id = transaction_id
        self.save()


class Voucher(models.Model):
    code = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    # Masa berlaku
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    usage_limit = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Maksimal jumlah penggunaan (kosong = tidak terbatas)"
    )
    used_count = models.PositiveIntegerField(default=0)
    one_time_per_user = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} - Rp {self.amount:,.0f}"

    def is_valid_for_user(self, user):
        now = timezone.now().date()

        if not self.is_active:
            return False, "Voucher tidak aktif."

        if self.start_date and now < self.start_date:
            return False, "Voucher belum aktif."

        if self.end_date and now > self.end_date:
            return False, "Voucher sudah kadaluarsa."

        if self.usage_limit is not None and self.used_count >= self.usage_limit:
            return False, "Voucher sudah mencapai batas penggunaan."

        if self.one_time_per_user and VoucherUsage.objects.filter(user=user, voucher=self).exists():
            return False, "Voucher hanya bisa digunakan satu kali per pengguna."

        return True, ""


class VoucherUsage(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'voucher')  # untuk one_time_per_user




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
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    voucher = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    merchant_ref = models.CharField(max_length=100, unique=True, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True, help_text='ID unik pembayaran dari gateway')
    payment_method = models.CharField(max_length=50, null=True, blank=True)
    payment_url = models.URLField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)