import uuid
from django.db import models
from django.conf import settings


class DashboardWidget(models.Model):
    WIDGET_CHART    = 'chart'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    WIDGET_KPI      = 'kpi'
    WIDGET_TABLE    = 'table'
    WIDGET_TEXT     = 'text'
    WIDGET_INSIGHTS = 'insights'
    WIDGET_TYPES = [
        (WIDGET_CHART,    'Chart'),
        (WIDGET_KPI,      'KPI Card'),
        (WIDGET_TABLE,    'Data Table'),
        (WIDGET_TEXT,     'Text / Note'),
        (WIDGET_INSIGHTS, 'AI Insights'),
    ]
    SIZE_SM   = '1x1'
    SIZE_MD   = '2x1'
    SIZE_LG   = '3x1'
    SIZE_TALL = '2x2'
    SIZE_CHOICES = [
        (SIZE_SM,   'Small (1×1)'),
        (SIZE_MD,   'Medium (2×1)'),
        (SIZE_LG,   'Wide (3×1)'),
        (SIZE_TALL, 'Large (2×2)'),
    ]

    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='widgets')
    title       = models.CharField(max_length=100)
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPES)
    size        = models.CharField(max_length=5, choices=SIZE_CHOICES, default=SIZE_MD)
    sort_order  = models.PositiveIntegerField(default=0)
    # Source references
    upload      = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE,
                                    null=True, blank=True, related_name='widgets')
    chart_config = models.ForeignKey('analyser.ChartConfig', on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='widgets')
    # Config
    config      = models.JSONField(default=dict)   # column, metric, text content, etc.
    is_visible  = models.BooleanField(default=True)
    refresh_mins = models.PositiveSmallIntegerField(default=0)  # 0 = no auto-refresh
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'created_at']

    def __str__(self):
        return f"{self.title} ({self.widget_type})"
