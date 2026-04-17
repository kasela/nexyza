import uuid
from django.db import models
from django.conf import settings


class DataSnapshot(models.Model):
    """Immutable snapshot of a FileUpload's analysis_result at a point in time."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload       = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE, related_name='snapshots')
    version      = models.PositiveIntegerField()
    label        = models.CharField(max_length=100, blank=True)
    analysis     = models.JSONField()
    row_count    = models.PositiveIntegerField()
    column_count = models.PositiveIntegerField()
    diff_from_prev = models.JSONField(null=True, blank=True)   # delta vs previous snapshot
    triggered_by = models.CharField(max_length=50, default='manual')  # manual, pipeline, api
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version']
        unique_together = ('upload', 'version')

    def __str__(self):
        return f"{self.upload.original_name} v{self.version} ({self.row_count} rows)"
