import json
import time
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .models import SensorReading, IrrigationLog, SystemConfig
from .ml_predictor import predict_irrigation


def _now_ms() -> int:
    return int(time.time() * 1000)


def _stop_pump(cfg: SystemConfig, current_soil: float, note: str):
    if not cfg.pump_on:
        return
    now = _now_ms()
    IrrigationLog.objects.create(
        start_ms=cfg.pump_start_ms or now,
        end_ms=now,
        src=cfg.pump_src,
        soil0=cfg.pump_soil0,
        soil1=current_soil,
        note=note,
        skipped=False,
    )
    cfg.pump_on = False
    cfg.pump_stop_at = None
    cfg.save()


def _start_pump(cfg: SystemConfig, src: str, duration_sec: int, current_soil: float, stop_at=None):
    if cfg.pump_on:
        return
    now = _now_ms()
    cfg.pump_on = True
    cfg.pump_src = src
    cfg.pump_start_ms = now
    cfg.pump_end_ms = now + int(duration_sec * 1000)
    cfg.pump_soil0 = current_soil
    cfg.pump_stop_at = stop_at
    cfg.save()


def dashboard_view(request):
    return render(request, "irrigation/dashboard.html")


@csrf_exempt
def api_sensor_ingest(request):
    """
    Endpoint untuk Board ESP (POST /api/sensor/):
    Body JSON dari ESP:
      {"soil": 42.5, "temp": 32.1, "rh": 55.0}
      (mendukung juga alias kolom dataset Colab: {"MOI": 42.5, "temp": 32.1, "humidity": 55.0})
    """
    if request.method != "POST":
        return JsonResponse({"error": "Gunakan method POST dengan JSON {soil, temp, rh}"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
        soil = round(float(payload.get("soil", payload.get("MOI", 50.0))), 1)
        temp = round(float(payload.get("temp", 27.0)), 1)
        rh = round(float(payload.get("rh", payload.get("humidity", 70.0))), 1)
    except Exception as e:
        return JsonResponse({"error": f"Invalid JSON: {e}"}, status=400)

    now = _now_ms()
    cfg = SystemConfig.get_solo()
    pred = predict_irrigation(soil, temp, rh, seedling_stage=cfg.seedling_stage)

    if cfg.pump_on:
        if cfg.pump_stop_at is not None and soil >= cfg.pump_stop_at:
            _stop_pump(cfg, soil, f"Tanah mencapai batas basah {cfg.pump_stop_at}%")
        elif now >= cfg.pump_end_ms:
            _stop_pump(cfg, soil, "Waktu habis, mati otomatis" if cfg.pump_src == "manual" else "Durasi siklus selesai")

    if not cfg.pump_on and cfg.mode == "ml":
        if pred["water"] and soil < cfg.wet_limit:
            _start_pump(cfg, "ml", duration_sec=15, current_soil=soil, stop_at=cfg.wet_limit)

    reading = SensorReading.objects.create(
        timestamp_ms=now,
        soil=soil,
        temp=temp,
        rh=rh,
        pump_on=cfg.pump_on,
        ml_water=pred["water"],
        ml_prob=pred["p"],
    )

    total_count = SensorReading.objects.count()
    if total_count > 1500:
        oldest_ids = list(SensorReading.objects.order_by("timestamp_ms").values_list("id", flat=True)[: total_count - 1440])
        SensorReading.objects.filter(id__in=oldest_ids).delete()

    return JsonResponse({
        "ok": True,
        "pump": cfg.pump_on,
        "mode": cfg.mode,
        "seedling_stage": cfg.seedling_stage,
        "wet_limit": cfg.wet_limit,
        "ml_water": pred["water"],
        "ml_prob": pred["p"],
        "engine": pred["engine"],
        "timestamp": reading.timestamp_ms,
    })


def api_dashboard_state(request):
    cfg = SystemConfig.get_solo()
    now = _now_ms()

    latest = SensorReading.objects.order_by("-timestamp_ms").first()
    cur_soil = latest.soil if latest else 65.0
    cur_temp = latest.temp if latest else 27.5
    cur_rh = latest.rh if latest else 70.0

    if cfg.pump_on and now >= cfg.pump_end_ms:
        _stop_pump(cfg, cur_soil, "Waktu habis, mati otomatis")

    pred = predict_irrigation(cur_soil, cur_temp, cur_rh, seedling_stage=cfg.seedling_stage)

    readings = list(SensorReading.objects.order_by("-timestamp_ms")[:360])
    readings.reverse()
    hist = [
        {"t": r.timestamp_ms, "soil": r.soil, "temp": r.temp, "rh": r.rh, "pump": 1 if r.pump_on else 0}
        for r in readings
    ]

    logs = [
        {
            "start": l.start_ms,
            "end": l.end_ms,
            "src": l.src,
            "soil0": l.soil0,
            "soil1": l.soil1,
            "note": l.note,
            "skipped": l.skipped,
        }
        for l in IrrigationLog.objects.order_by("-start_ms")[:20]
    ]
    logs.reverse()

    esp_online = (latest is not None) and ((now - latest.timestamp_ms) < 15000)

    return JsonResponse({
        "now": now,
        "esp_online": esp_online,
        "last_seen_ms": latest.timestamp_ms if latest else None,
        "cur": {"soil": cur_soil, "temp": cur_temp, "rh": cur_rh},
        "ml": pred,
        "mode": cfg.mode,
        "seedlingStage": cfg.seedling_stage,
        "wetLimit": cfg.wet_limit,
        "pump": cfg.pump_on,
        "session": {
            "src": cfg.pump_src,
            "start": cfg.pump_start_ms,
            "endBy": cfg.pump_end_ms,
            "soil0": cfg.pump_soil0,
            "stopAt": cfg.pump_stop_at,
        } if cfg.pump_on else None,
        "schedules": json.loads(cfg.schedules_json),
        "hist": hist,
        "log": logs,
    })


@csrf_exempt
def api_dashboard_control(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    cfg = SystemConfig.get_solo()
    latest = SensorReading.objects.order_by("-timestamp_ms").first()
    cur_soil = latest.soil if latest else 65.0

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

    action = data.get("action")
    if action == "set_mode":
        new_mode = data.get("mode", "ml")
        if cfg.pump_on:
            _stop_pump(cfg, cur_soil, "Dihentikan karena mode diganti")
        cfg.mode = new_mode
        cfg.save()
    elif action == "set_stage":
        cfg.seedling_stage = data.get("seedling_stage", "Flowering")
        cfg.save()
    elif action == "toggle_manual":
        dur_sec = int(data.get("duration_sec", 5))
        if cfg.pump_on:
            _stop_pump(cfg, cur_soil, "Dimatikan dari dashboard")
        else:
            _start_pump(cfg, "manual", duration_sec=dur_sec, current_soil=cur_soil, stop_at=None)
    elif action == "emergency_stop":
        _stop_pump(cfg, cur_soil, "Dihentikan darurat dari dashboard")
        cfg.mode = "manual"
        cfg.save()
    elif action == "set_wet_limit":
        cfg.wet_limit = max(60, min(90, int(data.get("wet_limit", 75))))
        cfg.save()
    elif action == "save_schedules":
        cfg.schedules_json = json.dumps(data.get("schedules", []))
        cfg.save()

    return api_dashboard_state(request)
