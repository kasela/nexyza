from django.contrib import admin
from .models import WorkspaceRole
@admin.register(WorkspaceRole)
class WorkspaceRoleAdmin(admin.ModelAdmin):
    list_display = ("name","team","is_default","created_at")
