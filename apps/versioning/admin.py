from django.contrib import admin
from .models import DataSnapshot
@admin.register(DataSnapshot)
class DataSnapshotAdmin(admin.ModelAdmin):
    list_display = ('upload','version','label','row_count','triggered_by','created_at')
    readonly_fields = ('analysis','diff_from_prev')
