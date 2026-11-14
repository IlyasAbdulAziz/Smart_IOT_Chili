# 🌱 Smart Agriculture: Sistem Irigasi Cabai (Django + TabPFN + ESP)
**Tim: "Denger Azan Kok Lanjut Pidato"**

Folder ini berisi aplikasi Web Dashboard & Backend API berbasis **Django** dan **TabPFN Classification** untuk mengendalikan irigasi tanaman cabai.

---

## 📂 Struktur Folder Project
* `manage.py` & `smart_chili/` — Konfigurasi utama project **Django**.
* `irrigation/` — Aplikasi utama Django:
  * `models.py` — Tabel database SQLite (`SensorReading`, `IrrigationLog`, `SystemConfig`).
  * `ml_predictor.py` — **Mesin Machine Learning TabPFN** (tempat temanmu menaruh model/dataset).
  * `views.py` & `urls.py` — Endpoint API untuk Board ESP (`/api/sensor/`) dan Web Dashboard (`/api/state/`, `/api/control/`).
  * `templates/irrigation/dashboard.html` — Desain Web Dashboard interaktif dengan fitur **Mode Simulasi** & **Mode Alat Live (ESP + Django)**.
* `dataset/chili_irrigation_sample.csv` — Contoh dataset pelatihan (`soil_moisture, temperature, air_humidity, water`).
* `standalone_server.py` — Server alternatif siap jalan **tanpa perlu install library tambahan** (cocok untuk langsung tes sekarang).
* `tes_kirim_sensor_esp.py` — Simulator untuk mengetes pengiriman data seolah-olah dari ESP ke server.

---

## 🚀 Cara Menjalankan (Ada 2 Cara)

### Cara Cepat (Langsung Jalan Tanpa Install Apa-apa)
Buka terminal di folder ini, lalu jalankan:
```powershell
python standalone_server.py
```
Lalu buka browser ke: **`http://127.0.0.1:8000`**

### Cara Standar Django (Jika Ingin Pakai Django Penuh + `/admin`)
1. Install library yang dibutuhkan:
   ```powershell
   pip install -r requirements.txt
   ```
2. Buat tabel database SQLite dan jalankan server:
   ```powershell
   python manage.py makemigrations irrigation
   python manage.py migrate
   python manage.py runserver 0.0.0.0:8000
   ```

---

## 🤝 Panduan untuk Temanmu yang Ngoding Machine Learning (TabPFN)
Temanmu cukup melihat file **`irrigation/ml_predictor.py`**:
1. **Opsi 1 (Pakai Dataset CSV):** Ganti isi file `dataset/chili_irrigation_sample.csv` dengan dataset asli kalian (pastikan nama kolomnya: `soil_moisture,temperature,air_humidity,water`). Saat server dijalankan dan `tabpfn` sudah terinstall, `TabPFNClassifier` otomatis men-training data tersebut!
2. **Opsi 2 (Pakai File `.pkl`):** Jika temanmu sudah men-training `TabPFNClassifier` di Google Colab/Jupyter dan menyimpannya dengan `pickle.dump()`, cukup taruh file-nya di `dataset/tabpfn_model.pkl`. Sistem otomatis mendeteksi dan memakainya!
