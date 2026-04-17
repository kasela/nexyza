import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
import secrets


class User(AbstractUser):
    email      = models.EmailField(unique=True)
    avatar     = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio        = models.CharField(max_length=200, blank=True)
    timezone   = models.CharField(max_length=60, default='UTC')
    is_email_verified = models.BooleanField(default=False)
    email_verify_token = models.CharField(max_length=64, blank=True)
    # 2FA
    totp_secret      = models.CharField(max_length=32, blank=True)
    totp_enabled     = models.BooleanField(default=False)
    # Preferences
    notify_on_pipeline = models.BooleanField(default=True)
    notify_on_alert    = models.BooleanField(default=True)
    notify_digest      = models.BooleanField(default=True)
    # Metadata
    last_seen  = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def initials(self):
        parts = (self.first_name, self.last_name)
        return ''.join(p[0].upper() for p in parts if p) or self.email[0].upper()

    @property
    def is_pro(self):
        return hasattr(self, 'subscription') and self.subscription.is_active

    def generate_email_token(self):
        self.email_verify_token = secrets.token_urlsafe(48)
        return self.email_verify_token


class OnboardingState(models.Model):
    """Tracks which onboarding steps a user has completed."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user              = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='onboarding')
    welcomed          = models.BooleanField(default=False)
    first_upload      = models.BooleanField(default=False)
    viewed_charts     = models.BooleanField(default=False)
    asked_nlq         = models.BooleanField(default=False)
    invited_team      = models.BooleanField(default=False)
    dismissed         = models.BooleanField(default=False)

    @property
    def progress(self):
        steps = [self.first_upload, self.viewed_charts, self.asked_nlq]
        return int(sum(steps) / len(steps) * 100)

    @property
    def is_complete(self):
        return self.dismissed or self.progress >= 100
