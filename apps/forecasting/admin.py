from django.contrib import admin
from .models import Forecast
@admin.register(Forecast)
class ForecastAdmin(admin.ModelAdmin):
    list_display = ("upload","date_column","value_column","periods","method","created_at")
