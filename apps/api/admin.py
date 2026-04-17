from django.contrib import admin
from .models import APIKey

@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('prefix', 'name', 'user', 'is_active', 'last_used', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('user__email', 'prefix')
    readonly_fields = ('key', 'prefix', 'created_at', 'last_used')
