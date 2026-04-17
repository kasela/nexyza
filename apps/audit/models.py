import uuid
from django.db import models
from django.conf import settings


class AuditEvent(models.Model):
    ACTION_UPLOAD   = 'upload'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ACTION_VIEW     = 'view'
    ACTION_EXPORT   = 'export'
    ACTION_DELETE   = 'delete'
    ACTION_SHARE    = 'share'
    ACTION_AI_QUERY = 'ai_query'
    ACTION_NLQ      = 'nlq'
    ACTION_LOGIN    = 'login'
    ACTION_API_CALL = 'api_call'
    ACTION_CHART_GEN = 'chart_gen'

    ACTION_CHOICES = [
        (ACTION_UPLOAD,   'Upload'),
        (ACTION_VIEW,     'View'),
        (ACTION_EXPORT,   'Export'),
        (ACTION_DELETE,   'Delete'),
        (ACTION_SHARE,    'Share'),
        (ACTION_AI_QUERY, 'AI Query'),
        (ACTION_NLQ,      'NL Query'),
        (ACTION_LOGIN,    'Login'),
        (ACTION_API_CALL, 'API Call'),
        (ACTION_CHART_GEN, 'Chart Generate'),
    ]

    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, related_name='audit_events')
    action     = models.CharField(max_length=20, choices=ACTION_CHOICES)
    resource   = models.CharField(max_length=200, blank=True)   # e.g. "FileUpload:42"
    detail     = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    timestamp  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} {self.action} {self.resource} @ {self.timestamp}"


def log_event(request, action, resource='', detail=None):
    """Convenience function to log an audit event."""
    user = request.user if request and request.user.is_authenticated else None
    ip   = _get_ip(request)
    ua   = request.META.get('HTTP_USER_AGENT', '')[:300] if request else ''
    AuditEvent.objects.create(
        user=user, action=action, resource=resource,
        detail=detail or {}, ip_address=ip, user_agent=ua,
    )


def _get_ip(request):
    if not request:
        return None
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
