import uuid
from django.db import models
from django.conf import settings


class ScheduledReport(models.Model):
    FREQ_WEEKLY  = 'weekly'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    FREQ_MONTHLY = 'monthly'
    FREQ_CHOICES = [(FREQ_WEEKLY, 'Weekly'), (FREQ_MONTHLY, 'Monthly')]

    DAY_CHOICES = [(i, d) for i, d in enumerate(
        ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'])]

    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reports')
    name        = models.CharField(max_length=100)
    uploads     = models.ManyToManyField('analyser.FileUpload', blank=True)
    frequency   = models.CharField(max_length=10, choices=FREQ_CHOICES, default=FREQ_WEEKLY)
    send_day    = models.PositiveSmallIntegerField(default=0, choices=DAY_CHOICES,
                                                   help_text='Day of week (0=Mon) or day of month (1-28)')
    send_hour   = models.PositiveSmallIntegerField(default=8)
    recipient_email = models.EmailField()
    include_ai_summary = models.BooleanField(default=True)
    is_active   = models.BooleanField(default=True)
    last_sent   = models.DateTimeField(null=True, blank=True)
    next_send   = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.frequency})"
