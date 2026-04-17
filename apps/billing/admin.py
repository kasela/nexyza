from django.contrib import admin
from .models import Subscription, WebhookEvent


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'is_active', 'current_period_end', 'updated_at')
    list_filter = ('plan', 'status')
    search_fields = ('user__email', 'ls_subscription_id', 'ls_customer_id')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ('event_name', 'event_id', 'processed', 'created_at')
    list_filter = ('event_name', 'processed')
    readonly_fields = ('event_id', 'event_name', 'payload', 'processed', 'created_at')
