"""
Server Cadangan Siap Jalan (Zero-Install) untuk Smart Chili IoT
Menyajikan template `irrigation/templates/irrigation/dashboard.html`,
Database SQLite (`db.sqlite3`), dan modul `irrigation/ml_predictor.py` (TabPFN 4-Fitur)
di http://127.0.0.1:8000 (atau http://0.0.0.0:8000 untuk diakses ESP via Wi-Fi).
"""
import json
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from irrigation.ml_predictor import predict_irrigation

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db.sqlite3"
HTML_PATH = BASE_DIR / "irrigation" / "templates" / "irrigation" / "dashboard.html"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS irrigation_sensorreading (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_ms INTEGER,
            soil REAL,
            temp REAL,
            rh REAL,
            pump_on INTEGER,
            ml_water INTEGER,
            ml_prob REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS irrigation_irrigationlog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_ms INTEGER,
            end_ms INTEGER,
            src TEXT,
            soil0 REAL,
            soil1 REAL,
            note TEXT,
            skipped INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS irrigation_systemconfig (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            mode TEXT,
            seedling_stage TEXT DEFAULT 'Flowering',
            wet_limit INTEGER,
            pump_on INTEGER,
            pump_src TEXT,
            pump_start_ms INTEGER,
            pump_end_ms INTEGER,
            pump_soil0 REAL,
            pump_stop_at INTEGER,
            schedules_json TEXT
        )
    """)
    # Pastikan kolom seedling_stage ada jika tabel sudah pernah dibuat sebelumnya
    cols = [row[1] for row in c.execute("PRAGMA table_info(irrigation_systemconfig)").fetchall()]
    if "seedling_stage" not in cols:
        c.execute("ALTER TABLE irrigation_systemconfig ADD COLUMN seedling_stage TEXT DEFAULT 'Flowering'")

    c.execute("SELECT id FROM irrigation_systemconfig WHERE id = 1")
    if not c.fetchone():
        c.execute("""
            INSERT INTO irrigation_systemconfig
            (id, mode, seedling_stage, wet_limit, pump_on, pump_src, pump_start_ms, pump_end_ms, pump_soil0, pump_stop_at, schedules_json)
            VALUES (1, 'ml', 'Flowering', 75, 0, 'ml', 0, 0, 50.0, 75,
            '[{"id":1,"time":"06:00","dur":8,"on":true},{"id":2,"time":"12:00","dur":8,"on":true},{"id":3,"time":"17:00","dur":8,"on":true}]')
        """)
    conn.commit()
    conn.close()


def now_ms() -> int:
    return int(time.time() * 1000)


class SmartChiliHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            html_bytes = HTML_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.end_headers()
            self.wfile.write(html_bytes)
            return

        if self.path.startswith("/api/state"):
            self._handle_state()
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        if self.path.startswith("/api/sensor"):
            self._handle_sensor(body)
            return

        if self.path.startswith("/api/control"):
            self._handle_control(body)
            return

        self.send_error(404, "Not Found")

    def _stop_pump(self, conn, cfg, cur_soil: float, note: str):
        if not cfg["pump_on"]:
            return
        now = now_ms()
        conn.execute(
            "INSERT INTO irrigation_irrigationlog (start_ms, end_ms, src, soil0, soil1, note, skipped) VALUES (?, ?, ?, ?, ?, ?, 0)",
            (cfg["pump_start_ms"] or now, now, cfg["pump_src"], cfg["pump_soil0"], cur_soil, note),
        )
        conn.execute("UPDATE irrigation_systemconfig SET pump_on = 0, pump_stop_at = NULL WHERE id = 1")
        conn.commit()

    def _start_pump(self, conn, src: str, dur_sec: int, cur_soil: float, stop_at):
        now = now_ms()
        conn.execute(
            "UPDATE irrigation_systemconfig SET pump_on = 1, pump_src = ?, pump_start_ms = ?, pump_end_ms = ?, pump_soil0 = ?, pump_stop_at = ? WHERE id = 1",
            (src, now, now + int(dur_sec * 1000), cur_soil, stop_at),
        )
        conn.commit()

    def _handle_sensor(self, body: str):
        try:
            payload = json.loads(body)
            soil = round(float(payload.get("soil", payload.get("MOI", 50.0))), 1)
            temp = round(float(payload.get("temp", 27.0)), 1)
            rh = round(float(payload.get("rh", payload.get("humidity", 70.0))), 1)
        except Exception as e:
            self._send_json({"error": str(e)}, status=400)
            return

        now = now_ms()
        conn = get_db()
        cfg = dict(conn.execute("SELECT * FROM irrigation_systemconfig WHERE id = 1").fetchone())
        stage = cfg.get("seedling_stage") or "Flowering"
        pred = predict_irrigation(soil, temp, rh, seedling_stage=stage)

        if cfg["pump_on"]:
            if cfg["pump_stop_at"] is not None and soil >= cfg["pump_stop_at"]:
                self._stop_pump(conn, cfg, soil, f"Tanah mencapai batas basah {cfg['pump_stop_at']}%")
                cfg["pump_on"] = 0
            elif now >= cfg["pump_end_ms"]:
                self._stop_pump(conn, cfg, soil, "Waktu habis, mati otomatis" if cfg["pump_src"] == "manual" else "Durasi siklus selesai")
                cfg["pump_on"] = 0

        if not cfg["pump_on"] and cfg["mode"] == "ml":
            if pred["water"] and soil < cfg["wet_limit"]:
                self._start_pump(conn, "ml", 15, soil, cfg["wet_limit"])
                cfg["pump_on"] = 1

        conn.execute(
            "INSERT INTO irrigation_sensorreading (timestamp_ms, soil, temp, rh, pump_on, ml_water, ml_prob) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (now, soil, temp, rh, 1 if cfg["pump_on"] else 0, 1 if pred["water"] else 0, pred["p"]),
        )
        conn.commit()
        conn.close()

        self._send_json({
            "ok": True,
            "pump": bool(cfg["pump_on"]),
            "mode": cfg["mode"],
            "seedling_stage": stage,
            "wet_limit": cfg["wet_limit"],
            "ml_water": pred["water"],
            "ml_prob": pred["p"],
            "engine": pred["engine"],
            "timestamp": now,
        })

    def _handle_state(self):
        now = now_ms()
        conn = get_db()
        cfg = dict(conn.execute("SELECT * FROM irrigation_systemconfig WHERE id = 1").fetchone())
        latest = conn.execute("SELECT * FROM irrigation_sensorreading ORDER BY timestamp_ms DESC LIMIT 1").fetchone()

        cur_soil = latest["soil"] if latest else 65.0
        cur_temp = latest["temp"] if latest else 27.5
        cur_rh = latest["rh"] if latest else 70.0

        if cfg["pump_on"] and now >= cfg["pump_end_ms"]:
            self._stop_pump(conn, cfg, cur_soil, "Waktu habis, mati otomatis")
            cfg = dict(conn.execute("SELECT * FROM irrigation_systemconfig WHERE id = 1").fetchone())

        stage = cfg.get("seedling_stage") or "Flowering"
        pred = predict_irrigation(cur_soil, cur_temp, cur_rh, seedling_stage=stage)

        rows = conn.execute("SELECT * FROM irrigation_sensorreading ORDER BY timestamp_ms DESC LIMIT 360").fetchall()
        hist = [
            {"t": r["timestamp_ms"], "soil": r["soil"], "temp": r["temp"], "rh": r["rh"], "pump": r["pump_on"]}
            for r in reversed(rows)
        ]

        log_rows = conn.execute("SELECT * FROM irrigation_irrigationlog ORDER BY start_ms DESC LIMIT 20").fetchall()
        logs = [
            {
                "start": l["start_ms"],
                "end": l["end_ms"],
                "src": l["src"],
                "soil0": l["soil0"],
                "soil1": l["soil1"],
                "note": l["note"],
                "skipped": bool(l["skipped"]),
            }
            for l in reversed(log_rows)
        ]
        conn.close()

        esp_online = (latest is not None) and ((now - latest["timestamp_ms"]) < 15000)
        self._send_json({
            "now": now,
            "esp_online": esp_online,
            "cur": {"soil": cur_soil, "temp": cur_temp, "rh": cur_rh},
            "ml": pred,
            "mode": cfg["mode"],
            "seedlingStage": stage,
            "wetLimit": cfg["wet_limit"],
            "pump": bool(cfg["pump_on"]),
            "session": {
                "src": cfg["pump_src"],
                "start": cfg["pump_start_ms"],
                "endBy": cfg["pump_end_ms"],
                "soil0": cfg["pump_soil0"],
                "stopAt": cfg["pump_stop_at"],
            } if cfg["pump_on"] else None,
            "schedules": json.loads(cfg["schedules_json"]),
            "hist": hist,
            "log": logs,
        })

    def _handle_control(self, body: str):
        data = json.loads(body)
        conn = get_db()
        cfg = dict(conn.execute("SELECT * FROM irrigation_systemconfig WHERE id = 1").fetchone())
        latest = conn.execute("SELECT * FROM irrigation_sensorreading ORDER BY timestamp_ms DESC LIMIT 1").fetchone()
        cur_soil = latest["soil"] if latest else 65.0

        action = data.get("action")
        if action == "set_mode":
            if cfg["pump_on"]:
                self._stop_pump(conn, cfg, cur_soil, "Dihentikan karena mode diganti")
            conn.execute("UPDATE irrigation_systemconfig SET mode = ? WHERE id = 1", (data.get("mode", "ml"),))
            conn.commit()
        elif action == "set_stage":
            conn.execute("UPDATE irrigation_systemconfig SET seedling_stage = ? WHERE id = 1", (data.get("seedling_stage", "Flowering"),))
            conn.commit()
        elif action == "toggle_manual":
            dur_sec = int(data.get("duration_sec", 5))
            if cfg["pump_on"]:
                self._stop_pump(conn, cfg, cur_soil, "Dimatikan dari dashboard")
            else:
                self._start_pump(conn, "manual", dur_sec, cur_soil, None)
        elif action == "emergency_stop":
            self._stop_pump(conn, cfg, cur_soil, "Dihentikan darurat dari dashboard")
            conn.execute("UPDATE irrigation_systemconfig SET mode = 'manual' WHERE id = 1")
            conn.commit()
        elif action == "set_wet_limit":
            wl = max(60, min(90, int(data.get("wet_limit", 75))))
            conn.execute("UPDATE irrigation_systemconfig SET wet_limit = ? WHERE id = 1", (wl,))
            conn.commit()
        elif action == "save_schedules":
            conn.execute("UPDATE irrigation_systemconfig SET schedules_json = ? WHERE id = 1", (json.dumps(data.get("schedules", [])),))
            conn.commit()

        conn.close()
        self._handle_state()


if __name__ == "__main__":
    init_db()
    host, port = "0.0.0.0", 8000
    print("=" * 62, flush=True)
    print("🌱 SMART CHILI IRRIGATION SERVER (Django + TabPFN 4-Feature API)", flush=True)
    print(f"👉 Buka Dashboard di Browser : http://127.0.0.1:{port}", flush=True)
    print(f"👉 Atau lewat IP Wi-Fi Laptop: http://192.168.18.205:{port}", flush=True)
    print(f"👉 Endpoint untuk Board ESP  : http://192.168.18.205:{port}/api/sensor/", flush=True)
    print("=" * 62, flush=True)
    ThreadingHTTPServer((host, port), SmartChiliHandler).serve_forever()
