import uuid
from django.db import models
from django.conf import settings
from django.utils.crypto import get_random_string


class APIKey(models.Model):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_keys')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name       = models.CharField(max_length=100, default='Default')
    key        = models.CharField(max_length=64, unique=True)
    prefix     = models.CharField(max_length=10)
    is_active  = models.BooleanField(default=True)
    last_used  = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.prefix}… ({self.user.email})"

    @classmethod
    def generate(cls, user, name='Default'):
        raw = get_random_string(48)
        prefix = f"{settings.API_KEY_PREFIX}{raw[:6]}"
        return cls.objects.create(user=user, name=name, key=raw, prefix=prefix)

    def display_key(self):
        return f"{settings.API_KEY_PREFIX}{self.key}"

    def check_rate_limit(self) -> tuple[bool, str]:
        """
        Check if this key has exceeded its rate limit.
        Returns (allowed: bool, reason: str).
        Limits: 60 requests/min, 1000 requests/hour, 10000 requests/day.
        """
        from django.core.cache import cache
        from django.utils import timezone

        now   = timezone.now()
        key_m = f"rl_min_{self.pk}_{now.strftime('%Y%m%d%H%M')}"
        key_h = f"rl_hr_{self.pk}_{now.strftime('%Y%m%d%H')}"
        key_d = f"rl_day_{self.pk}_{now.strftime('%Y%m%d')}"

        # Per-plan limits
        sub = getattr(self.user, 'subscription', None)
        if sub and sub.is_active:
            lim_min, lim_hr, lim_day = 120, 2000, 20000
        else:
            lim_min, lim_hr, lim_day = 60, 1000, 10000

        count_m = (cache.get(key_m) or 0) + 1
        count_h = (cache.get(key_h) or 0) + 1
        count_d = (cache.get(key_d) or 0) + 1

        if count_m > lim_min:
            return False, f"Rate limit: {lim_min} requests/minute exceeded"
        if count_h > lim_hr:
            return False, f"Rate limit: {lim_hr} requests/hour exceeded"
        if count_d > lim_day:
            return False, f"Rate limit: {lim_day} requests/day exceeded"

        cache.set(key_m, count_m, timeout=60)
        cache.set(key_h, count_h, timeout=3600)
        cache.set(key_d, count_d, timeout=86400)
        return True, ""
