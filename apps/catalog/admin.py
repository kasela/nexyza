from django.contrib import admin
from .models import DataAsset, LineageEdge
@admin.register(DataAsset)
class DataAssetAdmin(admin.ModelAdmin):
    list_display = ("name","owner","domain","source_type","quality_score","is_verified","is_sensitive")
    list_filter  = ("source_type","is_verified","is_sensitive")
admin.site.register(LineageEdge)
