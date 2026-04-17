from django.contrib import admin
from .models import Webhook, WebhookDelivery
@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ("name","user","url","is_active","success_count","failure_count")
admin.site.register(WebhookDelivery)
