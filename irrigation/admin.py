from django.contrib import admin
from .models import SensorReading, IrrigationLog, SystemConfig


@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = ("created_at", "soil", "temp", "rh", "pump_on", "ml_water", "ml_prob")
    list_filter = ("pump_on", "ml_water")


@admin.register(IrrigationLog)
class IrrigationLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "src", "soil0", "soil1", "note", "skipped")
    list_filter = ("src", "skipped")


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ("mode", "wet_limit", "pump_on", "pump_src", "updated_at")
