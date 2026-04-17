import uuid
from django.db import models
from django.conf import settings


class DataSource(models.Model):
    SOURCE_URL  = 'url'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    SOURCE_UPLOAD = 'upload'
    SOURCE_CHOICES = [(SOURCE_URL, 'URL'), (SOURCE_UPLOAD, 'Re-Upload')]

    FREQ_HOURLY  = 'hourly'
    FREQ_DAILY   = 'daily'
    FREQ_WEEKLY  = 'weekly'
    FREQ_MONTHLY = 'monthly'
    FREQ_CHOICES = [
        (FREQ_HOURLY,  'Every Hour'),
        (FREQ_DAILY,   'Daily'),
        (FREQ_WEEKLY,  'Weekly'),
        (FREQ_MONTHLY, 'Monthly'),
    ]

    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pipelines')
    name        = models.CharField(max_length=100)
    source_type = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_URL)
    source_url  = models.URLField(blank=True)
    frequency   = models.CharField(max_length=10, choices=FREQ_CHOICES, default=FREQ_DAILY)
    is_active   = models.BooleanField(default=True)
    last_run    = models.DateTimeField(null=True, blank=True)
    next_run    = models.DateTimeField(null=True, blank=True)
    last_upload = models.ForeignKey('analyser.FileUpload', on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='+')
    run_count   = models.PositiveIntegerField(default=0)
    last_error  = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    def __str__(self):
        return f"{self.name} ({self.frequency})"


class PipelineRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    STATUS_OK    = 'ok'
    STATUS_ERROR = 'error'
    STATUS_CHOICES = [(STATUS_OK, 'OK'), (STATUS_ERROR, 'Error')]

    source      = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='runs')
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES)
    upload      = models.ForeignKey('analyser.FileUpload', on_delete=models.SET_NULL, null=True)
    rows_before = models.PositiveIntegerField(default=0)
    rows_after  = models.PositiveIntegerField(default=0)
    error       = models.TextField(blank=True)
    ran_at      = models.DateTimeField(auto_now_add=True)
