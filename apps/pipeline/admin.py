from django.contrib import admin
from .models import DataSource, PipelineRun

@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'source_type', 'frequency', 'is_active', 'run_count', 'last_run')

@admin.register(PipelineRun)
class PipelineRunAdmin(admin.ModelAdmin):
    list_display = ('source', 'status', 'rows_before', 'rows_after', 'ran_at')
