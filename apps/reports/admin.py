from django.contrib import admin
from .models import ScheduledReport


@admin.register(ScheduledReport)
class ScheduledReportAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'frequency', 'is_active', 'last_sent', 'next_send')
    list_filter = ('frequency', 'is_active')
    search_fields = ('name', 'user__email', 'recipient_email')
