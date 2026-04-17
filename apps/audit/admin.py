from django.contrib import admin
from .models import AuditEvent

@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'resource', 'ip_address', 'timestamp')
    list_filter = ('action',)
    search_fields = ('user__email', 'resource')
    readonly_fields = ('user', 'action', 'resource', 'detail', 'ip_address', 'user_agent', 'timestamp')
