from django.contrib import admin
from .models import AnomalyReport
@admin.register(AnomalyReport)
class AnomalyReportAdmin(admin.ModelAdmin):
    list_display = ('upload','generated_at')
    readonly_fields = ('findings','summary')
