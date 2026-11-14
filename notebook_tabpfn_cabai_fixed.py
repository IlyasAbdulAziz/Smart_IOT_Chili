# -*- coding: utf-8 -*-
"""
Versi Rapih & Bebas Bug dari Notebook Google Colab Temanmu
(Sudah diperbaiki bagian import TabPFNClassifier Local vs Client)
"""

import os
import pandas as pd
import torch
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
    roc_auc_score,
)

# 1. Load Dataset dari Google Drive
url = "https://drive.google.com/uc?id=1a-5udyU0bueClq5pchocScDamvuK1ZDw"
df = pd.read_csv(url)

# 2. Filter khusus Tanaman Cabai (Chilli), Red Soil, selain Germination, dan result != 2
df_cabai = df[
    (df["crop ID"] == "Chilli")
    & (df["soil_type"] == "Red Soil")
    & (df["Seedling Stage"] != "Germination")
    & (df["result"] != 2)
].reset_index(drop=True)

print("Ukuran dataset cabai bersih:", df_cabai.shape)
print("Distribusi Kelas Target (result):")
print(df_cabai["result"].value_counts())

# 3. Pilih Backend TabPFN (Local GPU vs Cloud Client)
# PERBAIKAN BUG: Sebelumnya tertulis `TabPFNRegressor`, sekarang sudah benar `TabPFNClassifier`!
device = "cuda" if torch.cuda.is_available() else "cpu"
BACKEND = "local" if device == "cuda" else "client"
print(f"Device: {device} | Backend: {BACKEND}")

if BACKEND == "local":
    from tabpfn import TabPFNClassifier
    clf = TabPFNClassifier(device="cuda")
else:
    import tabpfn_client
    from tabpfn_client import TabPFNClassifier
    try:
        from google.colab import userdata
        token = userdata.get("TABPFN_TOKEN")
    except Exception:
        token = os.environ.get("TABPFN_TOKEN")

    if not token:
        raise ValueError("TABPFN_TOKEN tidak ditemukan di Colab Secrets / Environment.")
    tabpfn_client.set_access_token(token.strip())
    clf = TabPFNClassifier()

# 4. Split Data (80% Train, 20% Test)
feature_cols = ["Seedling Stage", "MOI", "temp", "humidity"]
target_col = "result"
X = df_cabai[feature_cols].copy()
y = df_cabai[target_col].copy()

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# 5. Latih Model TabPFNClassifier
clf.fit(X_train, y_train)
print(f"Model TabPFNClassifier ({BACKEND}) berhasil dilatih!")

# 6. Evaluasi Model
y_pred = clf.predict(X_test)
y_prob = clf.predict_proba(X_test)

acc = accuracy_score(y_test, y_pred)
roc_auc = roc_auc_score(y_test, y_prob[:, 1])
print(f"Accuracy: {acc:.4f} ({acc * 100:.2f}%)")
print(f"ROC-AUC : {roc_auc:.4f}")
print("\nClassification Report:")
print(classification_report(y_test, y_pred))

# 7. Export Dataset Bersih ke CSV (untuk dimasukkan ke folder `dataset/chili_irrigation_sample.csv` di Django!)
df_cabai.to_csv("chili_irrigation_sample.csv", index=False)
print("Dataset bersih disimpan ke `chili_irrigation_sample.csv` — siap dipakai di Django!")
