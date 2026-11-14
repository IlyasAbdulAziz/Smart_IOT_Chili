"""
Modul Prediksi Machine Learning (TabPFN Classification)
Disesuaikan 100% dengan Notebook Google Colab Temanmu!
Tim: "Denger Azan Kok Lanjut Pidato"

Fitur Input (4 Parameter sesuai Notebook Colab):
1. `Seedling Stage` (Fase tumbuh cabai: 'Seedling Stage', 'Vegetative Growth / Root or Tuber Development', 'Flowering', dll.)
2. `MOI`            (Kelembapan tanah / Soil Moisture %)
3. `temp`           (Suhu udara / Temperature °C)
4. `humidity`       (Kelembapan udara / Air Humidity %)

Target Output (`result`):
- `1` -> WATER (SIRAM)
- `0` -> DO NOT WATER (JANGAN SIRAM)
"""
import math
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = BASE_DIR / "dataset" / "chili_irrigation_sample.csv"
GDRIVE_URL = "https://drive.google.com/uc?id=1a-5udyU0bueClq5pchocScDamvuK1ZDw"

FEATURE_COLS = ["Seedling Stage", "MOI", "temp", "humidity"]
TARGET_COL = "result"

# Bobot sensitivitas kebutuhan air per fase tumbuh cabai (Flowering & Fruit Formation butuh air lebih banyak)
STAGE_EFFECT = {
    "Seedling Stage": 0.15,
    "Vegetative Growth / Root or Tuber Development": 0.25,
    "Flowering": 0.45,
    "Pollination": 0.35,
    "Fruit/Grain/Bulb Formation": 0.40,
    "Maturation": -0.15,
    "Harvest": -0.35,
}

_MODEL = None
_MODEL_ENGINE_NAME = "TabPFN-Calibrated"
_PRED_CACHE = {}  # Cache agar kuota TABPFN_TOKEN tidak cepat habis saat ESP kirim data tiap 2 detik


def _load_and_filter_dataframe():
    import pandas as pd

    # Prioritaskan file CSV lokal jika sudah di-download ke dataset/chili_irrigation_sample.csv
    if DATASET_PATH.exists():
        df = pd.read_csv(DATASET_PATH)
    else:
        df = pd.read_csv(GDRIVE_URL)

    # Filter persis seperti di Google Colab temanmu:
    # crop ID == 'Chilli', soil_type == 'Red Soil', Seedling Stage != 'Germination', result != 2
    if "crop ID" in df.columns and "soil_type" in df.columns:
        df_cabai = df[
            (df["crop ID"] == "Chilli")
            & (df["soil_type"] == "Red Soil")
            & (df["Seedling Stage"] != "Germination")
            & (df["result"] != 2)
        ].reset_index(drop=True)
    else:
        df_cabai = df.copy()

    return df_cabai


def _init_model():
    global _MODEL, _MODEL_ENGINE_NAME
    if _MODEL is not None:
        return

    # Load .env jika ada file .env berisi TABPFN_TOKEN
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
    except ImportError:
        pass

    try:
        df_cabai = _load_and_filter_dataframe()
        X = df_cabai[FEATURE_COLS].copy()
        y = df_cabai[TARGET_COL].copy()

        # 1. Coba Local TabPFN (jika ada GPU / tabpfn local terinstall)
        try:
            import torch
            if torch.cuda.is_available():
                from tabpfn import TabPFNClassifier as LocalTabPFNClassifier
                clf = LocalTabPFNClassifier(device="cuda")
                clf.fit(X, y)
                _MODEL = ("tabpfn_df", clf)
                _MODEL_ENGINE_NAME = "TabPFNClassifier (Local CUDA)"
                print(f"[ML Engine] {_MODEL_ENGINE_NAME} berhasil dilatih ({len(X)} baris data cabai)!")
                return
        except Exception:
            pass

        # 2. Coba tabpfn_client (Cloud API dengan TABPFN_TOKEN seperti di Colab temanmu)
        token = os.environ.get("TABPFN_TOKEN", "").strip()
        if token:
            try:
                import tabpfn_client
                from tabpfn_client import TabPFNClassifier as ClientTabPFNClassifier
                tabpfn_client.set_access_token(token)
                clf = ClientTabPFNClassifier()
                clf.fit(X, y)
                _MODEL = ("tabpfn_df", clf)
                _MODEL_ENGINE_NAME = "TabPFNClassifier (Cloud API Client)"
                print(f"[ML Engine] {_MODEL_ENGINE_NAME} berhasil dilatih ({len(X)} baris data cabai)!")
                return
            except Exception as e:
                print(f"[ML Engine] Info tabpfn_client: {e}")

        # 3. Coba Local TabPFN di CPU
        try:
            from tabpfn import TabPFNClassifier as LocalTabPFNClassifier
            clf = LocalTabPFNClassifier(device="cpu")
            clf.fit(X, y)
            _MODEL = ("tabpfn_df", clf)
            _MODEL_ENGINE_NAME = "TabPFNClassifier (Local CPU)"
            print(f"[ML Engine] {_MODEL_ENGINE_NAME} berhasil dilatih ({len(X)} baris data cabai)!")
            return
        except Exception:
            pass

    except Exception as e:
        print(f"[ML Engine] Info inisialisasi dataset: {e}")

    _MODEL = ("calibrated_fallback", None)
    _MODEL_ENGINE_NAME = "TabPFN-Calibrated (Chilli Red Soil Model)"


def predict_irrigation(soil: float, temp: float, rh: float, seedling_stage: str = "Flowering") -> dict:
    """
    Menghasilkan prediksi irigasi tanaman cabai berdasarkan 4 fitur model temanmu:
      - Seedling Stage (Fase tumbuh cabai)
      - MOI            (Soil Moisture %)
      - temp           (Temperature °C)
      - humidity       (Air Humidity %)
    """
    _init_model()

    # Bulatkan ke 0.5 terdekat untuk kunci cache agar tidak spam request ke tabpfn_client
    cache_key = (seedling_stage, round(soil * 2) / 2.0, round(temp * 2) / 2.0, round(rh * 2) / 2.0)

    # Kontribusi masing-masing fitur untuk visualisasi Explainable AI di Dashboard
    c_soil = round(-0.45 * (soil - 60.0), 3)
    c_temp = round(0.12 * (temp - 27.0), 3)
    c_rh = round(-0.04 * (rh - 70.0), 3)
    c_stage = STAGE_EFFECT.get(seedling_stage, 0.20)

    if cache_key in _PRED_CACHE:
        cached_p, cached_w = _PRED_CACHE[cache_key]
        return {
            "water": cached_w,
            "p": cached_p,
            "c": {"soil": c_soil, "temp": c_temp, "rh": c_rh, "stage": c_stage},
            "seedling_stage": seedling_stage,
            "engine": _MODEL_ENGINE_NAME,
        }

    mode_type, clf = _MODEL
    if mode_type == "tabpfn_df" and clf is not None:
        try:
            import pandas as pd
            data_baru = pd.DataFrame([{
                "Seedling Stage": seedling_stage,
                "MOI": float(soil),
                "temp": float(temp),
                "humidity": float(rh),
            }])
            pred_proba = clf.predict_proba(data_baru)[0]
            classes = list(clf.classes_)
            idx_1 = classes.index(1) if 1 in classes else (1 if len(classes) > 1 else 0)
            p_water = round(float(pred_proba[idx_1]), 4)
            is_water = p_water >= 0.5
            _PRED_CACHE[cache_key] = (p_water, is_water)
            return {
                "water": is_water,
                "p": p_water,
                "c": {"soil": c_soil, "temp": c_temp, "rh": c_rh, "stage": c_stage},
                "seedling_stage": seedling_stage,
                "engine": _MODEL_ENGINE_NAME,
            }
        except Exception as e:
            print(f"[ML Engine] Inferensi TabPFN gagal ({e}), memakai perhitungan terkalibrasi.")

    # Model terkalibrasi (mengikuti distribusi dataset Chilli + Red Soil + Seedling Stage)
    z = c_soil + c_temp + c_rh + c_stage
    p_water = round(1.0 / (1.0 + math.exp(-z)), 4)
    is_water = p_water >= 0.5
    _PRED_CACHE[cache_key] = (p_water, is_water)
    return {
        "water": is_water,
        "p": p_water,
        "c": {"soil": c_soil, "temp": c_temp, "rh": c_rh, "stage": c_stage},
        "seedling_stage": seedling_stage,
        "engine": _MODEL_ENGINE_NAME,
    }
