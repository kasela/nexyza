from django.contrib import admin
from .models import ComputedColumn
@admin.register(ComputedColumn)
class ComputedColumnAdmin(admin.ModelAdmin):
    list_display = ('name','upload','expression','is_active','created_at')
