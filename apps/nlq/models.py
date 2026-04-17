import uuid
from django.db import models
from django.conf import settings


class NLQuery(models.Model):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload     = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE, related_name='nl_queries')
    question   = models.TextField()
    answer     = models.TextField(blank=True)
    sql        = models.TextField(blank=True)   # generated pandas code
    chart_data = models.JSONField(null=True, blank=True)
    tokens_used = models.PositiveIntegerField(default=0)
    error      = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
