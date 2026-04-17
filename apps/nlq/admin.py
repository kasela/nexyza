from django.contrib import admin
from .models import NLQuery

@admin.register(NLQuery)
class NLQueryAdmin(admin.ModelAdmin):
    list_display = ('user', 'upload', 'question', 'tokens_used', 'created_at')
    search_fields = ('question', 'user__email')
    readonly_fields = ('answer', 'sql', 'chart_data', 'tokens_used')
