from django.contrib import admin
from .models import FileUpload, SavedDashboard, ChartConfig, CleaningOperation


@admin.register(FileUpload)
class FileUploadAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'user', 'file_type', 'file_size_display', 'status',
                    'row_count', 'column_count', 'share_enabled', 'created_at')
    list_filter = ('file_type', 'status', 'share_enabled')
    search_fields = ('original_name', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'analysis_result', 'share_token')


@admin.register(SavedDashboard)
class SavedDashboardAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'share_enabled', 'created_at')
    search_fields = ('name', 'user__email')


@admin.register(ChartConfig)
class ChartConfigAdmin(admin.ModelAdmin):
    list_display = ('title', 'upload', 'chart_type', 'x_axis', 'y_axis', 'aggregation', 'created_at')
    list_filter = ('chart_type', 'aggregation')


@admin.register(CleaningOperation)
class CleaningOperationAdmin(admin.ModelAdmin):
    list_display = ('upload', 'op_type', 'rows_before', 'rows_after', 'applied_at')
    list_filter = ('op_type',)
