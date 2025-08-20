from django.contrib.auth.signals import user_logged_in
import threading
import logging
from decimal import Decimal
import datetime
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.fields.files import ImageFieldFile
from authentication.models import CustomUser
from .models import AuditLog
from .middleware import get_current_user
from .utils import get_request_info

logger = logging.getLogger(__name__)
_pre_save_instances = threading.local()

def convert_to_json_serializable(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, ImageFieldFile):
        return str(obj) if obj else None
    elif isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: convert_to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_json_serializable(i) for i in obj]
    elif hasattr(obj, '__dict__'):
        return str(obj)
    return obj

def get_changes(old, new):
    changes = {}
    for field in new._meta.fields:
        if field.name == 'id':
            continue
        old_val = getattr(old, field.name, None) if old else None
        new_val = getattr(new, field.name, None)
        if old_val != new_val and not (old_val is None and new_val == '') and not (new_val is None and old_val == ''):
            changes[field.name] = {'from': old_val, 'to': new_val}
    return changes

def get_instance_data(instance):
    return {field.name: convert_to_json_serializable(getattr(instance, field.name, None)) for field in instance._meta.fields}

@receiver(pre_save)
def store_old_instance(sender, instance, **kwargs):
    if sender._meta.app_label == 'audit':
        return
    try:
        _pre_save_instances.old_instance = sender.objects.get(pk=instance.pk)
    except ObjectDoesNotExist:
        _pre_save_instances.old_instance = None

@receiver(post_save)
def log_create_or_update(sender, instance, created, **kwargs):
    if sender._meta.app_label == 'audit':
        return

    user = get_current_user()
    if not user or not user.is_authenticated:
        return  # Jangan buat log jika tidak ada user yang login atau user tidak terautentikasi

    content_type = ContentType.objects.get_for_model(sender)
    ip_address, user_agent, device_type, request_path = get_request_info()

    try:
        if created:
            changes = {'from': None, 'to': get_instance_data(instance)}
            AuditLog.objects.create(
                user=user,
                action='create',
                content_type=content_type,
                object_id=str(instance.pk),
                changes=changes,
                ip_address=ip_address,
                user_agent=user_agent,
                device_type=device_type,
                request_path=request_path,
            )
        else:
            old_instance = getattr(_pre_save_instances, 'old_instance', None)
            changes = get_changes(old_instance, instance) if old_instance else None
            changes = convert_to_json_serializable(changes) if changes else None
            if changes:
                AuditLog.objects.create(
                    user=user,
                    action='update',
                    content_type=content_type,
                    object_id=str(instance.pk),
                    changes=changes,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    device_type=device_type,
                    request_path=request_path,
                )
    except Exception as e:
        logger.error(f"Error in audit log (post_save) for {sender.__name__} pk={instance.pk}: {e}")
    finally:
        if hasattr(_pre_save_instances, 'old_instance'):
            del _pre_save_instances.old_instance

@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    if sender._meta.app_label == 'audit':
        return

    user = get_current_user()
    if not user or not user.is_authenticated:
        return  # Jangan buat log jika tidak ada user yang login atau user tidak terautentikasi

    content_type = ContentType.objects.get_for_model(sender)
    ip_address, user_agent, device_type, request_path = get_request_info()

    try:
        changes = {'from': get_instance_data(instance), 'to': None}
        AuditLog.objects.create(
            user=user,
            action='delete',
            content_type=content_type,
            object_id=str(instance.pk),
            changes=changes,
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_type,
            request_path=request_path,
        )
    except Exception as e:
        logger.error(f"Error in audit log (post_delete) for {sender.__name__} pk={instance.pk}: {e}")


#Log Login ke Audit
@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    ip_address, user_agent, device_type, request_path = get_request_info()

    AuditLog.objects.create(
        user=user if isinstance(user, CustomUser) else None,
        action='login',
        content_type=ContentType.objects.get_for_model(CustomUser),
        object_id=str(user.pk),
        changes={'from': None, 'to': 'login'},
        ip_address=ip_address,
        user_agent=user_agent,
        device_type=device_type,
        request_path=request_path,
    )