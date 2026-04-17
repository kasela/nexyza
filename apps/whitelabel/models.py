import uuid
from django.db import models
from django.conf import settings


class BrandingConfig(models.Model):
    user             = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='branding')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    app_name         = models.CharField(max_length=60, default='Nexyza')
    logo             = models.ImageField(upload_to='branding/logos/', blank=True, null=True)
    favicon          = models.ImageField(upload_to='branding/favicons/', blank=True, null=True)
    primary_color    = models.CharField(max_length=7, default='#7c3aed')   # hex
    accent_color     = models.CharField(max_length=7, default='#3b82f6')
    bg_color         = models.CharField(max_length=7, default='#0d0b17')
    surface_color    = models.CharField(max_length=7, default='#1e1b2e')
    custom_css       = models.TextField(blank=True)
    hide_datalens_branding = models.BooleanField(default=False)
    custom_domain    = models.CharField(max_length=253, blank=True)
    updated_at       = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Branding for {self.user.email}"

    def css_variables(self):
        return (
            f":root{{"
            f"--color-primary:{self.primary_color};"
            f"--color-accent:{self.accent_color};"
            f"--color-bg:{self.bg_color};"
            f"--color-surface:{self.surface_color};"
            f"}}"
        )
