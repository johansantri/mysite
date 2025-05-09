from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils.timezone import now
from authentication.models import CustomUser

class AuditLog(models.Model):
    ACTIONS = (
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    )

    user = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_index=True,
    )
    action = models.CharField(max_length=10, choices=ACTIONS, db_index=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, db_index=True)
    object_id = models.CharField(max_length=255, db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    timestamp = models.DateTimeField(default=now, db_index=True)
    changes = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, null=True, blank=True)  # Diperpanjang

    class Meta:
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"{self.user} {self.action} {self.content_type} {self.object_id} at {self.timestamp}"