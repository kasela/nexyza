import uuid
from django.db import models


class AnomalyReport(models.Model):
    upload     = models.OneToOneField('analyser.FileUpload', on_delete=models.CASCADE, related_name='anomaly_report')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    summary    = models.TextField(blank=True)    # AI narrative
    findings   = models.JSONField(default=list)  # list of anomaly dicts
    generated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Anomalies for {self.upload.original_name}"
