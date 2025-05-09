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

    user = models.ForeignKey(CustomUser, null=True, blank=True, on_delete=models.SET_NULL,db_index=True)
    action = models.CharField(max_length=10, choices=ACTIONS)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)

    # object_id bisa berupa integer atau UUID, jadi kita ganti menjadi CharField
    object_id = models.CharField(max_length=255)
    
    # GenericForeignKey untuk mengaitkan dengan objek yang dimodifikasi
    content_object = GenericForeignKey('content_type', 'object_id')

    timestamp = models.DateTimeField(default=now)
    changes = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} {self.action} {self.content_type} {self.object_id} at {self.timestamp}"
