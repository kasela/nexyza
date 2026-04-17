import uuid
from django.db import models
from django.conf import settings
from django.utils.crypto import get_random_string


class Team(models.Model):
    name       = models.CharField(max_length=100)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug       = models.SlugField(unique=True)
    owner      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_teams')
    logo       = models.ImageField(upload_to='team_logos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def get_member_role(self, user):
        try:
            return self.memberships.get(user=user).role
        except TeamMembership.DoesNotExist:
            return None

    def can_user_admin(self, user):
        return user == self.owner or self.get_member_role(user) == 'admin'

    def can_user_write(self, user):
        role = self.get_member_role(user)
        return user == self.owner or role in ('admin', 'editor')

    def can_user_read(self, user):
        return user == self.owner or self.get_member_role(user) is not None


class TeamMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ROLE_ADMIN  = 'admin'
    ROLE_EDITOR = 'editor'
    ROLE_VIEWER = 'viewer'
    ROLE_CHOICES = [
        (ROLE_ADMIN,  'Admin'),
        (ROLE_EDITOR, 'Editor'),
        (ROLE_VIEWER, 'Viewer'),
    ]
    team       = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='memberships')
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='team_memberships')
    role       = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_VIEWER)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, related_name='sent_invites')
    joined_at  = models.DateTimeField(auto_now_add=True)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class Meta:
        unique_together = ('team', 'user')

    def __str__(self):
        return f"{self.user.email} @ {self.team.name} ({self.role})"


class TeamInvite(models.Model):
    team       = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='invites')
    email      = models.EmailField()
    role       = models.CharField(max_length=10, choices=TeamMembership.ROLE_CHOICES, default='viewer')
    token      = models.CharField(max_length=40, unique=True, default=get_random_string(40))
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    accepted   = models.BooleanField(default=False)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invite {self.email} → {self.team.name}"


class SharedUpload(models.Model):
    """A FileUpload shared into a team workspace."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team       = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='shared_uploads')
    upload     = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE, related_name='team_shares')
    shared_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    shared_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('team', 'upload')
