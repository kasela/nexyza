import uuid
from django.db import models
from django.conf import settings
from django.utils.crypto import get_random_string


class Report(models.Model):
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reports_built')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title       = models.CharField(max_length=150)
    description = models.CharField(max_length=300, blank=True)
    cover_color = models.CharField(max_length=7, default='#7c3aed')
    logo        = models.ImageField(upload_to='report_logos/', blank=True, null=True)
    sections    = models.JSONField(default=list)   # ordered list of section dicts
    share_token = models.CharField(max_length=40, blank=True, db_index=True)
    is_public   = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title

    def generate_share_token(self):
        self.share_token = get_random_string(36)
        return self.share_token


class ReportSection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    """Sections are stored in Report.sections JSON but also as DB rows for ordering."""
    SECTION_HEADING  = 'heading'
    SECTION_TEXT     = 'text'
    SECTION_CHART    = 'chart'
    SECTION_STATS    = 'stats'
    SECTION_TABLE    = 'table'
    SECTION_DIVIDER  = 'divider'
    SECTION_AI       = 'ai_insights'
    SECTION_FORECAST = 'forecast'
    SECTION_TYPES = [
        (SECTION_HEADING,  'Heading'),
        (SECTION_TEXT,     'Text Block'),
        (SECTION_CHART,    'Chart'),
        (SECTION_STATS,    'Statistics'),
        (SECTION_TABLE,    'Data Table'),
        (SECTION_DIVIDER,  'Divider'),
        (SECTION_AI,       'AI Insights'),
        (SECTION_FORECAST, 'Forecast'),
    ]
    report      = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='section_rows')
    section_type = models.CharField(max_length=20, choices=SECTION_TYPES)
    sort_order  = models.PositiveIntegerField(default=0)
    content     = models.JSONField(default=dict)   # type-specific data
    created_at  = models.DateTimeField(auto_now_add=True)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class Meta:
        ordering = ['sort_order']


class ScheduledReport(models.Model):
    """Scheduled automatic delivery of a report by email."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    FREQ_DAILY   = 'daily'
    FREQ_WEEKLY  = 'weekly'
    FREQ_MONTHLY = 'monthly'
    FREQ_CHOICES = [
        (FREQ_DAILY,   'Daily'),
        (FREQ_WEEKLY,  'Weekly'),
        (FREQ_MONTHLY, 'Monthly'),
    ]

    report       = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='schedules')
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    email        = models.EmailField(blank=True, help_text="Deliver to this email (defaults to account email)")
    frequency    = models.CharField(max_length=10, choices=FREQ_CHOICES, default=FREQ_WEEKLY)
    is_active    = models.BooleanField(default=True)
    next_send_at = models.DateTimeField(null=True, blank=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    run_count    = models.PositiveIntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.report.title} — {self.frequency} to {self.email or self.user.email}"

    def schedule_next(self):
        from django.utils import timezone
        from datetime import timedelta
        deltas = {'daily': 1, 'weekly': 7, 'monthly': 30}
        self.next_send_at = timezone.now() + timedelta(days=deltas.get(self.frequency, 7))



class ReportExportJob(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_DONE = 'done'
    STATUS_ERROR = 'error'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_DONE, 'Done'),
        (STATUS_ERROR, 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='export_jobs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='report_export_jobs')
    fmt = models.CharField(max_length=10, default='pdf')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    result_url = models.CharField(max_length=500, blank=True)
    error = models.TextField(blank=True)
    status_message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.report.title} · {self.fmt} · {self.status}"
