from django.db.models.signals import post_save
from django.dispatch import receiver
from courses.models import Certificate, Enrollment

@receiver(post_save, sender=Certificate)
def update_enrollment_certificate_issued(sender, instance, **kwargs):
    Enrollment.objects.filter(
        user=instance.user, course=instance.course
    ).update(certificate_issued=True)
