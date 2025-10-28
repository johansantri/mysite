# myapp/signals.py
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
from courses.models import Partner

logger = logging.getLogger(__name__)

def send_partner_email_html(user, subject, template_name, context):
    """Kirim email HTML ke partner"""
    if user.email:
        html_content = render_to_string(template_name, context)
        email = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.content_subtype = "html"
        email.send(fail_silently=False)
        logger.info(f"Email sent to {user.email}: {subject}")
    else:
        logger.warning(f"User {user.username} has no email, cannot send '{subject}'")

# Simpan status lama sebelum disave
@receiver(pre_save, sender=Partner)
def cache_old_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except sender.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

@receiver(post_save, sender=Partner)
def notify_partner_status_change(sender, instance, created, **kwargs):
    """
    Kirim notifikasi email otomatis saat partner dibuat atau status berubah.
    """
    if created:
        # Baru submit request
        send_partner_email_html(
            instance.user,
            'Partner Request Submitted',
            'email/partner_request_submitted.html',
            {'user': instance.user, 'partner': instance}
        )
        logger.info(f"Partner request created for {instance.user.username}")
    else:
        # Status berubah
        old_status = getattr(instance, '_old_status', None)
        if old_status != instance.status:
            logger.info(f"Partner status changed for {instance.user.username}: {instance.status}")
            send_partner_email_html(
                instance.user,
                'Partner Request Status Updated',
                'email/partner_request_status_updated.html',
                {'user': instance.user, 'partner': instance}
            )
