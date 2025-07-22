from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from payments.models import Payment
from courses.models import Enrollment

@receiver(post_save, sender=Payment)
def enroll_user_after_payment(sender, instance, created, **kwargs):
    print(f"🚨 Signal aktif: Payment ID={instance.id}, Status={instance.status}")

    if instance.status == 'completed':
        enrollment, created = Enrollment.objects.get_or_create(
            user=instance.user,
            course=instance.course,
            defaults={
                'enrolled_at': timezone.now(),
                'certificate_issued': False,
            }
        )
        if created:
            print(f"✅ User {instance.user} berhasil enroll ke {instance.course}")
        else:
            print(f"ℹ️ User {instance.user} sudah pernah terdaftar di {instance.course}")
