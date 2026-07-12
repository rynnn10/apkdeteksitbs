# ⚡ Quick Start - Training Model TBS

## Opsi 1: Pakai Dataset Publik (Recommended)

### Step 1: Setup Kaggle API
```powershell
pip install kaggle

# Download API key dari https://www.kaggle.com/settings/account
# Simpan ke: C:\Users\ACER\.kaggle\kaggle.json
```

### Step 2: Download Dataset
```powershell
python download_dataset.py --source kaggle
```

### Step 3: Train
```powershell
pip install -r requirements-training.txt
python train_model_tbs.py
```

---

## Opsi 2: Generate Synthetic Dataset (Testing Pipeline)

Jika belum siap download dataset, test pipeline dulu:

```powershell
python generate_synthetic_dataset.py
python train_model_tbs.py
```

Model akan jadi di `backend/model_output/model_tbs.tflite` (akurasi rendah karena synthetic, tapi bisa test workflow)

---

## Opsi 3: Manual Download (No Auth)

### Roboflow (Paling Mudah - No Account)
1. Buka: https://universe.roboflow.com/achmad-fahri-x6r0k/oil-palm-fruit-ripeness-7r3zr
2. Klik "Download Dataset"
3. Pilih format "Folder Structure"
4. Extract ke `dataset/`

### Mendeley
1. Buka: https://data.mendeley.com/datasets/424y96m6sw/1
2. Download (perlu sign up gratis)
3. Extract, organize manual ke struktur:
   ```
   dataset/
   ├── mentah/
   ├── kurang_matang/
   ├── matang/
   ├── terlalu_matang/
   └── busuk/
   ```

---

## After Training

```powershell
# Test model
cd backend
python main.py
# Buka http://localhost:8000/docs

# Build APK dengan model baru
cd ..
.\run.ps1
```

Model otomatis ter-load, badge berubah dari **DEMO** → **OFFLINE** (TFLite inference).

---

**Estimasi waktu:**
- Download dataset: 5-15 menit
- Training: 10-30 menit (CPU), 5-10 menit (GPU)
- Build APK: 2 menit

**Jika stuck, run synthetic test dulu untuk validasi pipeline.**
