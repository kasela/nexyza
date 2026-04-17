import uuid
from django.db import models
from django.conf import settings


class ComputedColumn(models.Model):
    upload     = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE, related_name='computed_cols')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name       = models.CharField(max_length=100)
    expression = models.TextField()          # e.g. "revenue / qty" or "price * 1.1"
    description = models.CharField(max_length=200, blank=True)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        unique_together = ('upload', 'name')

    def __str__(self):
        return f"{self.name} = {self.expression}"
