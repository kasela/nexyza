import uuid
from django.db import models


class Forecast(models.Model):
    METHOD_LINEAR = 'linear'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    METHOD_MOVING = 'moving_avg'
    METHOD_EXP    = 'exponential'
    METHOD_AI     = 'ai'
    METHOD_CHOICES = [
        (METHOD_LINEAR, 'Linear Trend'),
        (METHOD_MOVING, 'Moving Average'),
        (METHOD_EXP,    'Exponential Smoothing'),
        (METHOD_AI,     'AI-Powered (Claude)'),
    ]

    upload         = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE, related_name='forecasts')
    date_column    = models.CharField(max_length=255)
    value_column   = models.CharField(max_length=255)
    periods        = models.PositiveSmallIntegerField(default=6)
    method         = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_AI)
    forecast_data  = models.JSONField(null=True, blank=True)   # {labels, actuals, forecast, lower, upper}
    ai_narrative   = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
