import uuid
from django.db import models
from django.conf import settings


class CollabSession(models.Model):
    """Tracks who is currently viewing a FileUpload."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload      = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE, related_name='collab_sessions')
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    channel_name = models.CharField(max_length=255)
    cursor_tab  = models.CharField(max_length=30, default='overview')
    is_active   = models.BooleanField(default=True)
    joined_at   = models.DateTimeField(auto_now_add=True)
    last_seen   = models.DateTimeField(auto_now=True)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class Meta:
        unique_together = ('upload', 'user')


class CollabComment(models.Model):
    """Inline comments on a shared analysis."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload      = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE, related_name='comments')
    author      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    tab         = models.CharField(max_length=30, default='overview')
    column_ref  = models.CharField(max_length=255, blank=True)
    chart_ref   = models.CharField(max_length=255, blank=True)
    section_ref = models.CharField(max_length=255, blank=True)
    text        = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class CollabAction(models.Model):
    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_DONE = 'done'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In progress'),
        (STATUS_DONE, 'Done'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE, related_name='collab_actions')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_collab_actions')
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_collab_actions')
    chart_ref = models.CharField(max_length=255, blank=True)
    section_ref = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=255)
    detail = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['status', '-created_at']
