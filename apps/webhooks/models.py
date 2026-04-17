import uuid
from django.db import models
from django.conf import settings


class Webhook(models.Model):
    EVENT_UPLOAD_DONE   = 'upload.done'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    EVENT_UPLOAD_ERROR  = 'upload.error'
    EVENT_ALERT_FIRED   = 'alert.fired'
    EVENT_PIPELINE_RAN  = 'pipeline.ran'
    EVENT_SNAPSHOT      = 'version.snapshot'
    EVENT_FORECAST_DONE = 'forecast.done'
    EVENT_ANOMALY_DETECTED = 'anomaly.detected'
    EVENT_REPORT_SCHEDULED = 'report.scheduled'
    EVENT_EXPORT_DONE      = 'export.done'

    EVENT_CHOICES = [
        (EVENT_UPLOAD_DONE,       'File analysis complete'),
        (EVENT_UPLOAD_ERROR,      'File analysis failed'),
        (EVENT_ANOMALY_DETECTED,  'Anomaly detected'),
        (EVENT_FORECAST_DONE,     'Forecast complete'),
        (EVENT_PIPELINE_RAN,      'Pipeline run complete'),
        (EVENT_REPORT_SCHEDULED,  'Report scheduled / sent'),
        (EVENT_EXPORT_DONE,       'Export downloaded'),
        (EVENT_ALERT_FIRED,       'Notification alert fired'),
        (EVENT_SNAPSHOT,          'Data snapshot saved'),
    ]

    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='webhooks')
    name        = models.CharField(max_length=100)
    url         = models.URLField(max_length=500)
    events      = models.JSONField(default=list)   # list of event strings
    secret      = models.CharField(max_length=64, blank=True)
    is_active   = models.BooleanField(default=True)
    last_fired  = models.DateTimeField(null=True, blank=True)
    success_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    def __str__(self):
        return f"{self.name} → {self.url}"


class WebhookDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    STATUS_OK    = 'ok'
    STATUS_FAIL  = 'failed'
    STATUS_RETRY = 'retrying'

    webhook     = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name='deliveries')
    event       = models.CharField(max_length=50)
    payload     = models.JSONField()
    status      = models.CharField(max_length=10, default=STATUS_RETRY)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response    = models.TextField(blank=True)
    attempt     = models.PositiveSmallIntegerField(default=1)
    delivered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-delivered_at']
