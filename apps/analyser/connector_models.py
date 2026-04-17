"""
Live data connector models for Google Sheets and Excel Online.
Connectors pull live data and auto-refresh dashboards.
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class DataConnector(models.Model):
    """A live data source connection (Google Sheets or Excel Online)."""

    SOURCE_GOOGLE_SHEETS = 'google_sheets'
    SOURCE_EXCEL_ONLINE  = 'excel_online'
    SOURCE_CSV_URL = 'csv_url'
    SOURCE_POSTGRESQL = 'postgresql'
    SOURCE_MYSQL = 'mysql'
    SOURCE_SQLSERVER = 'sqlserver'
    SOURCE_REST_API = 'rest_api'
    SOURCE_CHOICES = [
        (SOURCE_GOOGLE_SHEETS, 'Google Sheets'),
        (SOURCE_EXCEL_ONLINE,  'Microsoft Excel Online'),
        (SOURCE_CSV_URL, 'CSV URL'),
        (SOURCE_POSTGRESQL, 'PostgreSQL'),
        (SOURCE_MYSQL, 'MySQL'),
        (SOURCE_SQLSERVER, 'SQL Server'),
        (SOURCE_REST_API, 'REST API'),
    ]

    user         = models.ForeignKey(settings.AUTH_USER_MODEL,
                                     on_delete=models.CASCADE,
                                     related_name='connectors')
    source       = models.CharField(max_length=30, choices=SOURCE_CHOICES)
    name         = models.CharField(max_length=200)

    # Sheet-specific / connector endpoint
    sheet_url    = models.URLField(max_length=500, blank=True)
    endpoint_url = models.URLField(max_length=500, blank=True)
    connection_config = models.JSONField(default=dict, blank=True)
    sheet_id     = models.CharField(max_length=200, blank=True)   # Google Sheet ID
    sheet_tab    = models.CharField(max_length=200, blank=True)   # Tab / worksheet name
    range_spec   = models.CharField(max_length=100, blank=True,
                                    default='A1',
                                    help_text="e.g. A1:Z1000 or leave blank for entire sheet")

    # OAuth tokens (encrypted in production — store in secrets manager)
    access_token  = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_expiry  = models.DateTimeField(null=True, blank=True)
    oauth_scope   = models.CharField(max_length=500, blank=True)

    # Auto-refresh
    refresh_interval_min = models.PositiveIntegerField(
        default=60,
        help_text="Auto-refresh interval in minutes (0 = manual only)"
    )
    last_synced_at   = models.DateTimeField(null=True, blank=True)
    next_sync_at     = models.DateTimeField(null=True, blank=True)
    sync_status      = models.CharField(max_length=20, default='idle',
                                        choices=[('idle','Idle'),
                                                 ('syncing','Syncing'),
                                                 ('error','Error'),
                                                 ('ok','OK')])
    sync_error       = models.TextField(blank=True)
    row_count        = models.PositiveIntegerField(default=0)

    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} — {self.source}: {self.name}"

    @property
    def is_due_for_sync(self) -> bool:
        if self.refresh_interval_min == 0:
            return False
        if self.next_sync_at is None:
            return True
        return timezone.now() >= self.next_sync_at

    def schedule_next_sync(self):
        from datetime import timedelta
        if self.refresh_interval_min > 0:
            self.next_sync_at = timezone.now() + timedelta(minutes=self.refresh_interval_min)
            self.save(update_fields=['next_sync_at'])

    @property
    def source_icon(self) -> str:
        return {'google_sheets': '📊', 'excel_online': '📗', 'csv_url': '🧾', 'postgresql': '🐘', 'mysql': '🛢️', 'sqlserver': '🏢', 'rest_api': '🔌'}.get(self.source, '📄')

    @property
    def source_label(self) -> str:
        return dict(self.SOURCE_CHOICES).get(self.source, self.source)


class ConnectorSyncLog(models.Model):
    STATUS_CHOICES = [
        ('syncing', 'Syncing'),
        ('ok', 'OK'),
        ('error', 'Error'),
    ]
    TRIGGER_CHOICES = [
        ('manual', 'Manual'),
        ('auto', 'Automatic'),
        ('retry', 'Retry'),
        ('initial', 'Initial'),
    ]

    connector = models.ForeignKey(DataConnector, on_delete=models.CASCADE, related_name='sync_logs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='syncing')
    trigger = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default='manual')
    row_count = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    schema_signature = models.CharField(max_length=64, blank=True)
    schema_columns = models.JSONField(default=list, blank=True)
    alerts = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.connector.name} [{self.status}] @ {self.started_at:%Y-%m-%d %H:%M}"


class ConnectorAlertRule(models.Model):
    RULE_SYNC_FAILED = 'sync_failed'
    RULE_ROW_DROP = 'row_drop'
    RULE_ROW_SPIKE = 'row_spike'
    RULE_SCHEMA_CHANGE = 'schema_change'
    RULE_STALE = 'stale'
    RULE_CHOICES = [
        (RULE_SYNC_FAILED, 'Sync Failed'),
        (RULE_ROW_DROP, 'Row Drop %'),
        (RULE_ROW_SPIKE, 'Row Spike %'),
        (RULE_SCHEMA_CHANGE, 'Schema Change'),
        (RULE_STALE, 'No Sync Timeout'),
    ]

    ACTION_NONE = ''
    ACTION_RETRY = 'retry'
    ACTION_NOTIFY = 'notify'
    ACTION_CHOICES = [
        (ACTION_NONE, 'No Action'),
        (ACTION_RETRY, 'Auto Retry'),
        (ACTION_NOTIFY, 'Notify'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connector = models.ForeignKey(DataConnector, on_delete=models.CASCADE, related_name='alert_rules')
    rule_type = models.CharField(max_length=40, choices=RULE_CHOICES)
    threshold = models.FloatField(null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['rule_type', '-created_at']
        unique_together = [('connector', 'rule_type', 'threshold', 'action')]

    def __str__(self):
        return f"{self.connector.name} · {self.rule_type}"



class RefreshJob(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connector = models.ForeignKey(DataConnector, on_delete=models.CASCADE, related_name='refresh_jobs')
    name = models.CharField(max_length=150)
    cron = models.CharField(max_length=120, blank=True)
    frequency = models.CharField(max_length=30, default='hourly')
    is_enabled = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']


class ScheduledAnalyticsRun(models.Model):
    DELIVERY_CHOICES = [
        ('email', 'Email'),
        ('in_app', 'In-App'),
        ('none', 'None'),
    ]
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('ok', 'OK'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='scheduled_analytics_runs')
    upload = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE, related_name='scheduled_runs')
    analysis_view = models.ForeignKey('analyser.AnalysisView', on_delete=models.SET_NULL, null=True, blank=True, related_name='scheduled_runs')
    title = models.CharField(max_length=150)
    cadence = models.CharField(max_length=30, default='weekly')
    delivery_mode = models.CharField(max_length=20, choices=DELIVERY_CHOICES, default='email')
    recipients = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


class AnalysisSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE, related_name='analysis_snapshots')
    connector = models.ForeignKey(DataConnector, on_delete=models.SET_NULL, null=True, blank=True, related_name='snapshots')
    summary_json = models.JSONField(default=dict, blank=True)
    chart_payloads_json = models.JSONField(default=list, blank=True)
    alerts_json = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
