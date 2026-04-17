import uuid
from django.db import models
from django.conf import settings


class NotificationRule(models.Model):
    OP_GT  = 'gt'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    OP_LT  = 'lt'
    OP_EQ  = 'eq'
    OP_PCT = 'pct_change'
    OP_CHOICES = [
        (OP_GT,  'Greater than'),
        (OP_LT,  'Less than'),
        (OP_EQ,  'Equals'),
        (OP_PCT, 'Changes by % or more'),
    ]

    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notif_rules')
    upload     = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE, related_name='notif_rules')
    name       = models.CharField(max_length=100)
    column     = models.CharField(max_length=255)
    metric     = models.CharField(max_length=20, default='mean',
                                  choices=[('mean','Mean'),('max','Max'),('min','Min'),
                                           ('null_pct','Null %'),('row_count','Row Count')])
    operator   = models.CharField(max_length=15, choices=OP_CHOICES, default=OP_GT)
    threshold  = models.FloatField()
    is_active  = models.BooleanField(default=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name}: {self.column} {self.metric} {self.operator} {self.threshold}"


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    LEVEL_INFO    = 'info'
    LEVEL_WARNING = 'warning'
    LEVEL_ALERT   = 'alert'
    LEVEL_CHOICES = [(LEVEL_INFO,'Info'),(LEVEL_WARNING,'Warning'),(LEVEL_ALERT,'Alert')]

    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    rule       = models.ForeignKey(NotificationRule, on_delete=models.SET_NULL, null=True, related_name='notifications')
    upload     = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE, related_name='notifications')
    level      = models.CharField(max_length=10, choices=LEVEL_CHOICES, default=LEVEL_WARNING)
    title      = models.CharField(max_length=200)
    body       = models.TextField()
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.level}] {self.title}"
