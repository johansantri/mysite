from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal

CustomUser = get_user_model()

class Payment(models.Model):
    PAYMENT_MODEL_CHOICES = [
        ('buy_first', 'Buy first, then enroll'),
        ('pay_for_exam', 'Enroll first, pay at exam'),
        ('pay_for_certificate', 'Enroll & take exam first, pay at certificate claim'),
        ('free', 'Free'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='payments')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='payments')
    payment_model = models.CharField(max_length=20, choices=PAYMENT_MODEL_CHOICES)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed')],
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.course.course_name} - {self.payment_model} - {self.status}"

    class Meta:
        unique_together = ('user', 'course', 'payment_model')

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