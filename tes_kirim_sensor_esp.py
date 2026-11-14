"""
Script Simulator Pengirim Data ESP32/ESP8266 -> Server Django
Gunakan script ini untuk mengetes mode "Alat Live (ESP + Django)" di Dashboard
sebelum board ESP dicolok!

Cara pakai:
1. Nyalakan server di terminal 1:
   python standalone_server.py   (atau: python manage.py runserver 0.0.0.0:8000)
2. Jalankan simulator ini di terminal 2:
   python tes_kirim_sensor_esp.py
"""
import random
import time
import requests

SERVER_URL = "http://127.0.0.1:8000/api/sensor/"

soil = 44.0  # Mulai dari kondisi tanah agak kering agar TabPFN memicu penyiraman
temp = 32.5
rh = 54.0
pump_on = False

print(f"Mengirim data simulasi ESP ke {SERVER_URL} setiap 2 detik... (Tekan Ctrl+C untuk berhenti)")

while True:
    # Jika pompa menyala dari server, kelembapan tanah naik; jika mati, perlahan turun
    if pump_on:
        soil = min(88.0, soil + random.uniform(2.5, 4.2))
    else:
        soil = max(25.0, soil - random.uniform(0.3, 0.8))

    temp = max(22.0, min(37.0, temp + random.uniform(-0.2, 0.2)))
    rh = max(40.0, min(90.0, rh + random.uniform(-0.5, 0.5)))

    payload = {
        "soil": round(soil, 1),
        "temp": round(temp, 1),
        "rh": round(rh, 1),
    }

    try:
        res = requests.post(SERVER_URL, json=payload, timeout=5)
        data = res.json()
        pump_on = data.get("pump", False)
        print(
            f"[ESP -> Server] Tanah={payload['soil']}% | Suhu={payload['temp']}°C | Udara={payload['rh']}%  "
            f"===>  Balasan Server: ML={'WATER' if data.get('ml_water') else 'DO NOT WATER'} "
            f"({int(data.get('ml_prob', 0)*100)}%) | POMPA={'MENYALA 💦' if pump_on else 'MATI'}"
        )
    except Exception as e:
        print(f"Gagal menghubungi server ({e}). Pastikan server sudah menyala di port 8000!")

    time.sleep(2)
