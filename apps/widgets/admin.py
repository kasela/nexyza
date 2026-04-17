from django.contrib import admin
from .models import DashboardWidget
@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ("title","user","widget_type","size","is_visible","created_at")
    list_filter  = ("widget_type","size")
