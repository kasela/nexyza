from django.contrib import admin
from .models import NotificationRule, Notification
@admin.register(NotificationRule)
class NotificationRuleAdmin(admin.ModelAdmin):
    list_display = ('name','user','upload','column','metric','operator','threshold','is_active')
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title','user','level','is_read','created_at')
    list_filter = ('level','is_read')
