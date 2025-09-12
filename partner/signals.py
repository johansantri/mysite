# signals.py
from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from courses.models import Certificate, Enrollment, UserActivityLog

@receiver(post_save, sender=Certificate)
def update_enrollment_certificate_issued(sender, instance, **kwargs):
    Enrollment.objects.filter(
        user=instance.user, course=instance.course
    ).update(certificate_issued=True)

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    UserActivityLog.objects.create(user=user, activity_type='login_view')
