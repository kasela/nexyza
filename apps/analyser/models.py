import uuid
from django.db import models
from django.conf import settings
from django.utils.crypto import get_random_string
import os

import json as _json
import math as _math


class SafeJSONEncoder(_json.JSONEncoder):
    """
    JSON encoder that handles every non-serialisable type pandas/numpy can produce:
    Timestamp, Period, NaT, NA, numpy scalars, ndarray, date/datetime objects.
    This is the safety net — catches anything _safe() in engine.py missed.
    """
    def default(self, obj):
        # pandas Timestamp / Period / NaT / NA
        try:
            import pandas as _pd
            if isinstance(obj, _pd.Timestamp):
                return obj.isoformat()
            if isinstance(obj, _pd.Period):
                return str(obj)
            if obj is _pd.NaT or obj is _pd.NA:
                return None
        except Exception:
            pass
        # numpy scalars and arrays
        try:
            import numpy as _np
            if isinstance(obj, _np.integer):
                return int(obj)
            if isinstance(obj, _np.floating):
                return None if (_np.isnan(obj) or _np.isinf(obj)) else float(obj)
            if isinstance(obj, _np.bool_):
                return bool(obj)
            if isinstance(obj, _np.ndarray):
                return obj.tolist()
        except Exception:
            pass
        # Python datetime / date
        try:
            import datetime
            if isinstance(obj, (datetime.datetime, datetime.date)):
                return obj.isoformat()
        except Exception:
            pass
        # Anything else: convert to string rather than crash
        try:
            return str(obj)
        except Exception:
            return None


def upload_path(instance, filename):
    return f'uploads/{instance.user.id}/{filename}'


class FileUpload(models.Model):
    FILE_TYPE_CSV   = 'csv'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    FILE_TYPE_EXCEL = 'excel'
    FILE_TYPE_JSON  = 'json'
    FILE_TYPE_CHOICES = [
        (FILE_TYPE_CSV,   'CSV'),
        (FILE_TYPE_EXCEL, 'Excel'),
        (FILE_TYPE_JSON,  'JSON'),
    ]
    STATUS_PENDING    = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE       = 'done'
    STATUS_ERROR      = 'error'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'), (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE, 'Done'),       (STATUS_ERROR, 'Error'),
    ]

    user             = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='uploads')
    file             = models.FileField(upload_to=upload_path)
    original_name    = models.CharField(max_length=255)
    file_type        = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES)
    file_size        = models.PositiveIntegerField(default=0)
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    row_count        = models.PositiveIntegerField(default=0)
    column_count     = models.PositiveIntegerField(default=0)
    active_sheet     = models.CharField(max_length=255, blank=True)
    available_sheets = models.JSONField(default=list, blank=True)
    analysis_result  = models.JSONField(null=True, blank=True, encoder=SafeJSONEncoder)
    ai_insights      = models.TextField(blank=True)
    error_message    = models.TextField(blank=True)
    share_token      = models.CharField(max_length=40, blank=True, db_index=True)
    share_enabled    = models.BooleanField(default=False)
    share_expires    = models.DateTimeField(null=True, blank=True)
    is_pinned        = models.BooleanField(default=False)
    label            = models.CharField(max_length=100, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.original_name} ({self.user.email})"

    @property
    def file_size_display(self):
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @property
    def extension(self):
        return os.path.splitext(self.original_name)[1].lower()

    def generate_share_token(self):
        self.share_token = get_random_string(36)
        return self.share_token


class SavedDashboard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dashboards')
    name          = models.CharField(max_length=100)
    description   = models.TextField(blank=True)
    uploads       = models.ManyToManyField(FileUpload, blank=True, related_name='dashboards')
    share_token   = models.CharField(max_length=40, blank=True, db_index=True)
    share_enabled = models.BooleanField(default=False)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.user.email})"

    def generate_share_token(self):
        self.share_token = get_random_string(36)
        return self.share_token


class ChartConfig(models.Model):
    """A single chart — auto-generated or user-created."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    CHART_TYPES = [
        ('bar',        'Bar'),
        ('horizontal_bar', 'Horizontal Bar'),
        ('line',       'Line'),
        ('area',       'Area'),
        ('rolling_line', 'Rolling Line'),
        ('cumulative_line', 'Cumulative Line'),
        ('variance_bar', 'Variance Bar'),
        ('pareto',     'Pareto'),
        ('waterfall',  'Waterfall'),
        ('bullet',     'Bullet'),
        ('progress_ring', 'Progress Ring'),
        ('scatter',    'Scatter'),
        ('pie',        'Pie'),
        ('doughnut',   'Doughnut'),
        ('histogram',  'Histogram'),
        ('heatmap',    'Heatmap'),
        ('kpi',        'KPI Card'),
    ]
    AGG_CHOICES = [
        ('sum', 'Sum'), ('mean', 'Mean'), ('count', 'Count'),
        ('min', 'Min'), ('max', 'Max'),
    ]
    SIZE_CHOICES = [
        ('sm',   'Small  (1/3)'),
        ('md',   'Medium (1/2)'),
        ('lg',   'Large  (2/3)'),
        ('full', 'Full Width'),
    ]
    COLOR_PALETTES = [
        ('violet', 'Violet'),
        ('blue',   'Blue'),
        ('emerald','Emerald'),
        ('amber',  'Amber'),
        ('rose',   'Rose'),
        ('cyan',   'Cyan'),
        ('multi',  'Multi-color'),
    ]

    upload      = models.ForeignKey(FileUpload, on_delete=models.CASCADE, related_name='chart_configs')
    title       = models.CharField(max_length=150, default='')
    chart_type  = models.CharField(max_length=20, choices=CHART_TYPES, default='bar')
    x_axis      = models.CharField(max_length=255, blank=True)
    y_axis      = models.CharField(max_length=255, blank=True)
    group_by    = models.CharField(max_length=255, blank=True)
    aggregation = models.CharField(max_length=20, choices=AGG_CHOICES, default='sum')
    color       = models.CharField(max_length=20, choices=COLOR_PALETTES, default='violet')
    size        = models.CharField(max_length=8,  choices=SIZE_CHOICES,   default='md')
    sort_order  = models.PositiveIntegerField(default=0)
    is_auto     = models.BooleanField(default=False)   # True = auto-generated
    is_pinned   = models.BooleanField(default=False)
    # Raw chart data cached so we don't re-query on every page load
    cached_data = models.JSONField(null=True, blank=True)
    config_json = models.JSONField(default=dict)       # extra options
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'created_at']

    def __str__(self):
        return f"{self.title} ({self.upload.original_name})"


class AnalysisView(models.Model):
    VIEW_TYPES = [
        ('studio', 'Studio'),
        ('comparison', 'Comparison'),
        ('board', 'Board'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.ForeignKey(FileUpload, on_delete=models.CASCADE, related_name='analysis_views')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='analysis_views')
    title = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, blank=True)
    description = models.TextField(blank=True)
    view_type = models.CharField(max_length=20, choices=VIEW_TYPES, default='studio')
    filters_json = models.JSONField(default=dict, blank=True)
    kpi_config_json = models.JSONField(default=dict, blank=True)
    chart_order_json = models.JSONField(default=list, blank=True)
    layout_json = models.JSONField(default=dict, blank=True)
    drill_state_json = models.JSONField(default=dict, blank=True)
    selected_metrics_json = models.JSONField(default=list, blank=True)
    comparison_mode = models.CharField(max_length=30, blank=True, default='')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        unique_together = [('upload', 'user', 'title')]

    def __str__(self):
        return f"{self.title} ({self.upload.original_name})"



class CleaningOperation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    OP_TYPES = [
        ('drop_nulls',    'Drop Null Rows'),
        ('fill_nulls',    'Fill Nulls'),
        ('rename_column', 'Rename Column'),
        ('drop_column',   'Drop Column'),
        ('find_replace',  'Find & Replace'),
        ('filter_rows',   'Filter Rows'),
        ('change_dtype',  'Change Data Type'),
    ]
    upload      = models.ForeignKey(FileUpload, on_delete=models.CASCADE, related_name='cleaning_ops')
    op_type     = models.CharField(max_length=30, choices=OP_TYPES)
    params      = models.JSONField(default=dict)
    applied_at  = models.DateTimeField(auto_now_add=True)
    rows_before = models.PositiveIntegerField(default=0)
    rows_after  = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['applied_at']

# Live connectors (Google Sheets, Excel Online)
from .connector_models import DataConnector  # noqa


class UploadAnalysisProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.OneToOneField(FileUpload, on_delete=models.CASCADE, related_name='screening_profile')
    profile_json = models.JSONField(default=dict, blank=True)
    screening_json = models.JSONField(default=dict, blank=True)
    question_payload = models.JSONField(default=list, blank=True)
    requires_clarification = models.BooleanField(default=False)
    is_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']


class UploadClarificationResponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.OneToOneField(UploadAnalysisProfile, on_delete=models.CASCADE, related_name='clarification_response')
    response_json = models.JSONField(default=dict, blank=True)
    guidance_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']


class UploadConversationSession(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_READY = "ready"
    STATUS_FINISHED = "finished"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_READY, "Ready"),
        (STATUS_FINISHED, "Finished"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.OneToOneField(UploadAnalysisProfile, on_delete=models.CASCADE, related_name='conversation_session')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    current_question_key = models.CharField(max_length=120, blank=True)
    readiness_score = models.FloatField(default=0)
    confidence_json = models.JSONField(default=dict, blank=True)
    brief_json = models.JSONField(default=dict, blank=True)
    meta_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']


class UploadConversationTurn(models.Model):
    ROLE_ASSISTANT = "assistant"
    ROLE_USER = "user"
    ROLE_SYSTEM = "system"
    ROLE_CHOICES = [
        (ROLE_ASSISTANT, "Assistant"),
        (ROLE_USER, "User"),
        (ROLE_SYSTEM, "System"),
    ]

    KIND_MESSAGE = "message"
    KIND_QUESTION = "question"
    KIND_ANSWER = "answer"
    KIND_EVENT = "event"
    KIND_CHOICES = [
        (KIND_MESSAGE, "Message"),
        (KIND_QUESTION, "Question"),
        (KIND_ANSWER, "Answer"),
        (KIND_EVENT, "Event"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(UploadConversationSession, on_delete=models.CASCADE, related_name='turns')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_MESSAGE)
    question_key = models.CharField(max_length=120, blank=True)
    question_type = models.CharField(max_length=40, blank=True)
    message = models.TextField(blank=True)
    answer_value_json = models.JSONField(default=dict, blank=True)
    answer_label = models.TextField(blank=True)
    skipped = models.BooleanField(default=False)
    dont_know = models.BooleanField(default=False)
    confidence_before = models.FloatField(default=0)
    confidence_after = models.FloatField(default=0)
    meta_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']



class AdaptiveRefinementSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.OneToOneField(FileUpload, on_delete=models.CASCADE, related_name='adaptive_refinement')
    profile = models.ForeignKey(UploadAnalysisProfile, on_delete=models.CASCADE, related_name='adaptive_sessions')
    classification_json = models.JSONField(default=dict, blank=True)
    question_schema = models.JSONField(default=list, blank=True)
    answers_json = models.JSONField(default=dict, blank=True)
    recommendations_json = models.JSONField(default=dict, blank=True)
    current_step = models.PositiveIntegerField(default=0)
    is_complete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
