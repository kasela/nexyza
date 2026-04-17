from django.contrib import admin
from .models import JoinConfig
@admin.register(JoinConfig)
class JoinConfigAdmin(admin.ModelAdmin):
    list_display = ('name','user','left_upload','right_upload','join_type','created_at')
