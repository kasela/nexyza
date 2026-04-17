import uuid
from django.db import models
from django.conf import settings


class DataAsset(models.Model):
    """Metadata record for a FileUpload — the catalog entry."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    SOURCE_UPLOAD   = 'manual_upload'
    SOURCE_PIPELINE = 'pipeline'
    SOURCE_API      = 'api'
    SOURCE_JOIN     = 'join'
    SOURCE_CHOICES  = [
        (SOURCE_UPLOAD,   'Manual Upload'),
        (SOURCE_PIPELINE, 'Pipeline'),
        (SOURCE_API,      'API'),
        (SOURCE_JOIN,     'File Join'),
    ]

    upload      = models.OneToOneField('analyser.FileUpload', on_delete=models.CASCADE, related_name='catalog_entry')
    owner       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='catalog_assets')
    name        = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    tags        = models.CharField(max_length=300, blank=True)
    domain      = models.CharField(max_length=50, blank=True, help_text='e.g. Finance, Marketing')
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_UPLOAD)
    source_detail = models.TextField(blank=True)    # URL, pipeline name, etc.
    quality_score = models.FloatField(null=True, blank=True)   # 0-100
    is_verified = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(default=False, help_text='Contains PII or confidential data')
    refresh_frequency = models.CharField(max_length=20, blank=True)
    last_updated = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def tag_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    def compute_quality_score(self):
        """Simple quality score based on null %, column count, row count."""
        analysis = self.upload.analysis_result or {}
        cols = analysis.get('columns', [])
        if not cols:
            return 0
        avg_null = sum(c.get('null_pct', 0) for c in cols) / len(cols)
        has_rows = min(self.upload.row_count / 100, 1.0) * 30
        has_desc = 20 if self.description else 0
        has_tags = 10 if self.tags else 0
        null_score = max(0, 40 - avg_null)
        score = null_score + has_rows + has_desc + has_tags
        return round(min(score, 100), 1)


class LineageEdge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    """Directed edge: source → destination (how data flows/transforms)."""
    TRANSFORM_JOIN      = 'join'
    TRANSFORM_CLEAN     = 'clean'
    TRANSFORM_FORMULA   = 'formula'
    TRANSFORM_PIPELINE  = 'pipeline'
    TRANSFORM_EXPORT    = 'export'
    TRANSFORM_CHOICES   = [
        (TRANSFORM_JOIN,     'File Join'),
        (TRANSFORM_CLEAN,    'Data Cleaning'),
        (TRANSFORM_FORMULA,  'Computed Column'),
        (TRANSFORM_PIPELINE, 'Pipeline Refresh'),
        (TRANSFORM_EXPORT,   'Export'),
    ]

    source      = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE, related_name='lineage_outputs')
    destination = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE,
                                    null=True, blank=True, related_name='lineage_inputs')
    transform   = models.CharField(max_length=20, choices=TRANSFORM_CHOICES)
    detail      = models.CharField(max_length=300, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source.original_name} →[{self.transform}]→ {self.destination}"
