from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .models import AuditLog
from .middleware import get_current_user
from decimal import Decimal
import uuid
from authentication.models import CustomUser
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import redirect, render

def convert_decimal_to_float(obj):
    if isinstance(obj, Decimal):
        return float(obj)  # Convert Decimal to float
    elif isinstance(obj, dict):
        return {key: convert_decimal_to_float(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimal_to_float(item) for item in obj]
    return obj

def get_changes(old, new):
    changes = {}
    for field in new._meta.fields:
        field_name = field.name
        if field_name in ('id',):  # Jangan catat perubahan pada 'id'
            continue
        old_val = getattr(old, field_name, None)
        new_val = getattr(new, field_name, None)
        if old_val != new_val:
            changes[field_name] = {'from': old_val, 'to': new_val}
    return changes

@receiver(post_save)
def log_create_or_update(sender, instance, created, **kwargs):
    if sender._meta.app_label == 'audit': 
        return  # Hindari pencatatan untuk model AuditLog itu sendiri

    user = get_current_user()

    # Pastikan user adalah instance dari CustomUser, bukan AnonymousUser
    user_instance = user if isinstance(user, CustomUser) else None

    content_type = ContentType.objects.get_for_model(sender)

    if created:
        # Catat create
        AuditLog.objects.create(
            user=user_instance,  
            action='create',
            content_type=content_type,
            object_id=str(instance.pk),  # ID objek (bisa UUID atau integer)
            changes=None  # Tidak ada perubahan untuk create
        )
    else:
        try:
            old = sender.objects.get(pk=instance.pk)
            changes = get_changes(old, instance)
            changes = convert_decimal_to_float(changes)  # Convert Decimal to float
        except sender.DoesNotExist:
            changes = None

        # Catat update
        AuditLog.objects.create(
            user=user_instance,  
            action='update',
            content_type=content_type,
            object_id=str(instance.pk),  # ID objek yang dimodifikasi
            changes=changes
        )

@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    if sender._meta.app_label == 'audit': 
        return  # Hindari pencatatan untuk model AuditLog itu sendiri

    user = get_current_user()

    # Pastikan user adalah instance dari CustomUser, bukan AnonymousUser
    user_instance = user if isinstance(user, CustomUser) else None

    content_type = ContentType.objects.get_for_model(sender)

    # Catat delete
    AuditLog.objects.create(
        user=user_instance,  
        action='delete',
        content_type=content_type,
        object_id=str(instance.pk),  # ID objek yang dihapus
        changes=None  # Tidak ada perubahan untuk delete
    )