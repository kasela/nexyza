# No models needed — uses core analyser models
import uuid
from django.db import models
from django.conf import settings


class ExportJob(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_DONE    = 'done'
    STATUS_ERROR   = 'error'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_DONE,    'Done'),
        (STATUS_ERROR,   'Error'),
    ]

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='export_jobs')
    upload     = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE, related_name='export_jobs')
    fmt        = models.CharField(max_length=10)   # 'pdf' or 'pptx'
    theme      = models.CharField(max_length=30, default='dark')
    status     = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    result_url = models.CharField(max_length=500, blank=True)
    error      = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
