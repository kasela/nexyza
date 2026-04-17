import uuid
from django.db import models
from django.conf import settings


class Permission(models.TextChoices):
    # File permissions
    UPLOAD_FILES     = 'upload_files',     'Upload files'
    VIEW_FILES       = 'view_files',       'View files'
    DELETE_FILES     = 'delete_files',     'Delete files'
    EXPORT_FILES     = 'export_files',     'Export results'
    SHARE_FILES      = 'share_files',      'Create share links'
    # Analysis
    USE_AI           = 'use_ai',           'Use AI insights'
    USE_NLQ          = 'use_nlq',          'Natural language queries'
    RUN_FORECAST     = 'run_forecast',     'Run forecasts'
    # Team
    INVITE_MEMBERS   = 'invite_members',   'Invite team members'
    REMOVE_MEMBERS   = 'remove_members',   'Remove team members'
    MANAGE_ROLES     = 'manage_roles',     'Manage roles'
    # Data
    VIEW_AUDIT_LOG   = 'view_audit_log',   'View audit log'
    MANAGE_PIPELINES = 'manage_pipelines', 'Manage pipelines'
    MANAGE_WEBHOOKS  = 'manage_webhooks',  'Manage webhooks'
    # Reports
    BUILD_REPORTS    = 'build_reports',    'Build reports'
    PUBLISH_REPORTS  = 'publish_reports',  'Publish reports'


class WorkspaceRole(models.Model):
    """A custom role scoped to a team workspace."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team        = models.ForeignKey('teams.Team', on_delete=models.CASCADE, related_name='custom_roles')
    name        = models.CharField(max_length=60)
    description = models.CharField(max_length=200, blank=True)
    permissions = models.JSONField(default=list)   # list of Permission values
    is_default  = models.BooleanField(default=False)
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('team', 'name')

    def __str__(self):
        return f"{self.name} @ {self.team.name}"

    def has_permission(self, perm: str) -> bool:
        return perm in self.permissions


# Default role permission sets
DEFAULT_ROLE_PERMISSIONS = {
    'owner': list(Permission.values),
    'admin': [p for p in Permission.values if p not in ['manage_roles']],
    'editor': ['upload_files','view_files','delete_files','export_files','share_files',
               'use_ai','use_nlq','run_forecast','build_reports'],
    'viewer': ['view_files','export_files'],
    'analyst': ['view_files','export_files','use_ai','use_nlq','run_forecast',
                'build_reports','publish_reports'],
    'readonly': ['view_files'],
}
