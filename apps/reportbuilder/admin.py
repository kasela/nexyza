from django.contrib import admin
from .models import Report, ReportSection
@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("title","user","is_public","created_at")
admin.site.register(ReportSection)
