from django.contrib import admin
from .models import BrandingConfig

@admin.register(BrandingConfig)
class BrandingConfigAdmin(admin.ModelAdmin):
    list_display = ('user', 'app_name', 'hide_datalens_branding', 'updated_at')
