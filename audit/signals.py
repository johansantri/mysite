from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from .models import AuditLog
from .middleware import get_current_user, get_current_request
from decimal import Decimal
from authentication.models import CustomUser
from django.db.models.fields.files import ImageFieldFile
import logging
import datetime
import threading  # Pastikan Anda mengimpor threading di sini

logger = logging.getLogger(__name__)

# Simpan instance lama sebelum disimpan
_pre_save_instances = threading.local()

def convert_to_json_serializable(obj):
    """Convert objects to JSON-serializable formats recursively."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, ImageFieldFile):
        return str(obj) if obj else None
    elif isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat() if obj else None  # Konversi ke format ISO 8601
    elif isinstance(obj, dict):
        return {key: convert_to_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_json_serializable(item) for item in obj]
    elif hasattr(obj, '__dict__'):  # Tangani objek kustom
        return str(obj)
    return obj

def get_changes(old, new):
    """Compare old and new instance to get changed fields."""
    changes = {}
    for field in new._meta.fields:
        field_name = field.name
        if field_name in ('id',):  # Skip 'id' field
            continue
        old_val = getattr(old, field_name, None)
        new_val = getattr(new, field_name, None)
        if old_val != new_val and not (old_val is None and new_val == '') and not (new_val is None and old_val == ''):
            changes[field_name] = {'from': old_val, 'to': new_val}
    return changes

def get_request_info():
    """Extract IP address and user agent from current request."""
    request = get_current_request()
    if request and hasattr(request, 'audit_log_info'):
        return (
            request.audit_log_info.get('ip_address', None),
            request.audit_log_info.get('user_agent', None)
        )
    return None, None

@receiver(pre_save)
def store_old_instance(sender, instance, **kwargs):
    """Store the old instance before saving."""
    if sender._meta.app_label == 'audit':
        return
    try:
        old_instance = sender.objects.get(pk=instance.pk)
        _pre_save_instances.instance = old_instance
    except ObjectDoesNotExist:
        _pre_save_instances.instance = None

@receiver(post_save)
def log_create_or_update(sender, instance, created, **kwargs):
    """Log create or update actions to AuditLog."""
    if sender._meta.app_label == 'audit':
        return

    user = get_current_user()
    user_instance = user if isinstance(user, CustomUser) else None
    content_type = ContentType.objects.get_for_model(sender)
    ip_address, user_agent = get_request_info()

    try:
        if created:
            AuditLog.objects.create(
                user=user_instance,
                action='create',
                content_type=content_type,
                object_id=str(instance.pk),
                changes=None,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        else:
            old_instance = getattr(_pre_save_instances, 'instance', None)
            changes = get_changes(old_instance, instance) if old_instance else None
            changes = convert_to_json_serializable(changes) if changes else None

            if changes:
                AuditLog.objects.create(
                    user=user_instance,
                    action='update',
                    content_type=content_type,
                    object_id=str(instance.pk),
                    changes=changes,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
    except Exception as e:
        logger.error(f"Error in audit log (post_save) for model {sender.__name__}, instance {instance.pk}: {str(e)}")
    finally:
        # Bersihkan instance lama
        try:
            del _pre_save_instances.instance
        except AttributeError:
            pass

@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    """Log delete actions to AuditLog."""
    if sender._meta.app_label == 'audit':
        return

    user = get_current_user()
    user_instance = user if isinstance(user, CustomUser) else None
    content_type = ContentType.objects.get_for_model(sender)
    ip_address, user_agent = get_request_info()

    try:
        AuditLog.objects.create(
            user=user_instance,
            action='delete',
            content_type=content_type,
            object_id=str(instance.pk),
            changes=None,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception as e:
        logger.error(f"Error in audit log (post_delete) for model {sender.__name__}, instance {instance.pk}: {str(e)}")