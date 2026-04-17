import uuid
"""
Nexyza Billing Models
Supports: Free / Plus / Pro plans with AI token budgets and usage tracking.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class Plan(models.TextChoices):
    FREE         = 'free',         'Free'
    PLUS_MONTHLY = 'plus_monthly', 'Plus Monthly'
    PLUS_YEARLY  = 'plus_yearly',  'Plus Yearly'
    PRO_MONTHLY  = 'pro_monthly',  'Pro Monthly'
    PRO_YEARLY   = 'pro_yearly',   'Pro Yearly'


# ── Plan limits (all configurable via settings) ───────────────────────────────
PLAN_LIMITS = {
    'free': {
        'uploads_per_month':    5,
        'file_size_mb':         2,
        'ai_tokens_per_month':  0,        # no AI on free
        'max_rows':             10_000,
        'dashboards':           1,
        'connectors':           0,        # no live connectors
        'refresh_interval_min': None,     # no auto-refresh
        'collaborators':        0,
        'export_formats':       ['csv', 'json'],
        'support':              'community',
    },
    'plus': {
        'uploads_per_month':    50,
        'file_size_mb':         25,
        'ai_tokens_per_month':  200_000,  # ~200 AI chart generations
        'max_rows':             500_000,
        'dashboards':           10,
        'connectors':           2,        # Google Sheets + Excel Online
        'refresh_interval_min': 60,       # hourly auto-refresh
        'collaborators':        3,
        'export_formats':       ['csv', 'json', 'xlsx', 'pdf'],
        'support':              'email',
    },
    'pro': {
        'uploads_per_month':    None,     # unlimited
        'file_size_mb':         100,
        'ai_tokens_per_month':  2_000_000,
        'max_rows':             None,     # unlimited
        'dashboards':           None,
        'connectors':           None,     # all connectors
        'refresh_interval_min': 5,        # every 5 minutes
        'collaborators':        None,     # unlimited
        'export_formats':       ['csv', 'json', 'xlsx', 'pdf', 'pptx'],
        'support':              'priority',
    },
}


def _plan_key(plan: str) -> str:
    """Map variant plan name to limit key."""
    if 'plus' in plan:
        return 'plus'
    if 'pro' in plan:
        return 'pro'
    return 'free'


class Subscription(models.Model):
    user                 = models.OneToOneField(settings.AUTH_USER_MODEL,
                                                on_delete=models.CASCADE,
                                                related_name='subscription')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan                 = models.CharField(max_length=20, choices=Plan.choices,
                                            default=Plan.FREE)
    # LemonSqueezy IDs
    ls_subscription_id   = models.CharField(max_length=100, blank=True)
    ls_customer_id       = models.CharField(max_length=100, blank=True)
    ls_variant_id        = models.CharField(max_length=100, blank=True)
    status               = models.CharField(max_length=50, default='inactive')
    current_period_end   = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} — {self.plan}"

    @property
    def plan_key(self) -> str:
        return _plan_key(self.plan)

    @property
    def limits(self) -> dict:
        return PLAN_LIMITS[self.plan_key]

    @property
    def is_active(self) -> bool:
        return self.status in ('active', 'on_trial') and self.plan != Plan.FREE

    @property
    def is_plus(self) -> bool:
        return 'plus' in self.plan and self.is_active

    @property
    def is_pro(self) -> bool:
        return 'pro' in self.plan and self.is_active

    @property
    def is_paid(self) -> bool:
        return self.is_active

    @property
    def is_yearly(self) -> bool:
        return 'yearly' in self.plan

    @property
    def upload_limit(self):
        return self.limits['uploads_per_month']

    @property
    def file_size_limit(self) -> int:
        return self.limits['file_size_mb'] * 1024 * 1024

    @property
    def ai_token_budget(self) -> int:
        return self.limits['ai_tokens_per_month']

    @property
    def can_use_ai(self) -> bool:
        return self.limits['ai_tokens_per_month'] > 0

    @property
    def can_use_connectors(self) -> bool:
        c = self.limits['connectors']
        return c is None or c > 0

    @property
    def refresh_interval(self):
        return self.limits['refresh_interval_min']


class TokenUsage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    """Track AI token consumption per user per month."""
    user         = models.ForeignKey(settings.AUTH_USER_MODEL,
                                     on_delete=models.CASCADE,
                                     related_name='token_usage')
    year         = models.SmallIntegerField()
    month        = models.SmallIntegerField()
    tokens_used  = models.PositiveBigIntegerField(default=0)
    request_count= models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'year', 'month')
        indexes = [models.Index(fields=['user', 'year', 'month'])]

    def __str__(self):
        return f"{self.user.email} {self.year}/{self.month:02d} — {self.tokens_used:,} tokens"

    @classmethod
    def record(cls, user, tokens_in: int, tokens_out: int) -> 'TokenUsage':
        """Add tokens to this month's usage. Returns updated record."""
        now = timezone.now()
        obj, _ = cls.objects.get_or_create(
            user=user, year=now.year, month=now.month
        )
        obj.tokens_used   += tokens_in + tokens_out
        obj.request_count += 1
        obj.last_used_at   = now
        obj.save(update_fields=['tokens_used', 'request_count', 'last_used_at'])
        return obj

    @classmethod
    def this_month(cls, user) -> int:
        """Return tokens used this calendar month."""
        now = timezone.now()
        try:
            return cls.objects.get(
                user=user, year=now.year, month=now.month
            ).tokens_used
        except cls.DoesNotExist:
            return 0

    @classmethod
    def budget_remaining(cls, user) -> int | None:
        """Return remaining tokens, or None if unlimited."""
        try:
            budget = user.subscription.ai_token_budget
        except Exception:
            budget = 0
        if budget == 0:
            return 0
        if budget is None:
            return None
        used = cls.this_month(user)
        return max(0, budget - used)

    @classmethod
    def can_use_ai(cls, user) -> tuple[bool, str]:
        """Check if user can make an AI call. Returns (ok, reason)."""
        try:
            sub = user.subscription
        except Exception:
            return False, 'No subscription'
        if not sub.can_use_ai:
            return False, f'AI features require Plus or Pro plan'
        remaining = cls.budget_remaining(user)
        if remaining is not None and remaining <= 0:
            return False, f'Monthly AI token budget exhausted — resets on the 1st'
        return True, 'ok'


class WebhookEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id   = models.CharField(max_length=100, unique=True)
    event_name = models.CharField(max_length=100)
    payload    = models.JSONField()
    processed  = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_name} — {self.event_id}"
