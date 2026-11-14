from django.db import models


class SensorReading(models.Model):
    timestamp_ms = models.BigIntegerField(db_index=True)
    soil = models.FloatField(help_text="MOI / Kelembapan tanah (%)")
    temp = models.FloatField(help_text="temp / Suhu udara (°C)")
    rh = models.FloatField(help_text="humidity / Kelembapan udara (%)")
    pump_on = models.BooleanField(default=False)
    ml_water = models.BooleanField(default=False)
    ml_prob = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp_ms"]

    def __str__(self):
        return f"MOI={self.soil}% | Temp={self.temp}°C | RH={self.rh}% | Pump={'ON' if self.pump_on else 'OFF'}"


class IrrigationLog(models.Model):
    start_ms = models.BigIntegerField()
    end_ms = models.BigIntegerField()
    src = models.CharField(max_length=20, default="ml")  # 'manual', 'jadwal', 'ml'
    soil0 = models.FloatField(default=0.0)
    soil1 = models.FloatField(default=0.0)
    note = models.CharField(max_length=255, blank=True)
    skipped = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_ms"]

    def __str__(self):
        return f"[{self.src.upper()}] {self.soil0}% -> {self.soil1}% ({self.note})"


class SystemConfig(models.Model):
    mode = models.CharField(max_length=20, default="ml")  # 'manual', 'jadwal', 'ml'
    seedling_stage = models.CharField(max_length=80, default="Flowering")
    wet_limit = models.IntegerField(default=75)
    pump_on = models.BooleanField(default=False)
    pump_src = models.CharField(max_length=20, default="ml")
    pump_start_ms = models.BigIntegerField(default=0)
    pump_end_ms = models.BigIntegerField(default=0)
    pump_soil0 = models.FloatField(default=50.0)
    pump_stop_at = models.IntegerField(null=True, blank=True)
    schedules_json = models.TextField(
        default='[{"id":1,"time":"06:00","dur":8,"on":true},{"id":2,"time":"12:00","dur":8,"on":true},{"id":3,"time":"17:00","dur":8,"on":true}]'
    )
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
