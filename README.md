# 🌴 TBS Deteksi Kelapa Sawit

**Aplikasi Android native** untuk deteksi tingkat kematangan Tandan Buah Segar (TBS) kelapa sawit menggunakan AI Computer Vision dengan TensorFlow Lite.

Frontend React (Web) di-bundle ke dalam aplikasi Android (WebView) — bisa diinstall sebagai APK, tidak perlu server lokal untuk digunakan.

---

## ✨ Fitur

- 📸 **Upload foto** atau **ambil langsung dari kamera** (realtime)
- 🔍 **Klasifikasi 5 kategori**: Mentah, Kurang Matang, Matang, Terlalu Matang, Busuk
- ✅ **Confidence score (%)** tiap kategori + progress bar visual
- 💬 **Rekomendasi tindakan** per kategori (Layak panen / Tunggu / Tolak)
- 📋 **Riwayat deteksi** lengkap dengan timestamp (SQLite)
- 📊 **Dashboard statistik** — Pie chart distribusi + Bar chart tren harian (Recharts)
- 📱 **Mobile-friendly UI** — Tombol besar, kontras tinggi, akses kamera via browser

## 📱 Build APK Android

### Prasyarat

- **Java JDK 17+** (`java -version`)
- **Android SDK** (Android Studio atau command-line tools)
- **Node.js 18+** & npm
- **Gradle** (sudah ter-bundle via gradlew)

### 🚀 Quick Build (1 Klik)

```powershell
.\run.ps1
```

Script ini akan:
1. Build React frontend (`npm run build`)
2. Copy `dist/` ke `app/src/main/assets/`
3. Build APK via Gradle (`gradlew assembleDebug`)
4. Install APK via ADB ke device/emulator yang terhubung

**Output:** `app/build/outputs/apk/debug/app-debug.apk`

### ⌨️ Build dari VSCode

Tekan **Ctrl+Shift+B** (Windows/Linux) atau **Cmd+Shift+B** (Mac)

Pilih task:
- `Build APK (Gradle)` - Build APK (default)
- `Build & Install APK` - Build + install via ADB
- `Reinstall APK` - Install ulang tanpa rebuild

### 🛠️ Manual Build

```powershell
# 1. Build React
cd frontend
npm install
npm run build

# 2. Copy ke assets
cd ..
Copy-Item frontend\dist\* app\src\main\assets\ -Recurse -Force

# 3. Build APK
.\gradlew.bat assembleDebug

# 4. Install
adb install -r app\build\outputs\apk\debug\app-debug.apk
```

### 📦 Build Release (Signed APK)

Set environment variables sebelum build:

```powershell
$env:KEYSTORE_PATH="path\to\your-key.jks"
$env:STORE_PASSWORD="your-store-password"
$env:KEY_PASSWORD="your-key-password"

.\gradlew.bat assembleRelease
```

**Output:** `app/build/outputs/apk/release/app-release.apk`

---


---

## 🏗️ Arsitektur

```
┌─────────────────────────────────────────┐
│  Frontend (React + Vite)  :3000         │
│  DeteksiBaru → HasilDeteksi             │
│  Riwayat → Dashboard                    │
└──────────────┬──────────────────────────┘
               │ REST API (proxy)
┌──────────────▼──────────────────────────┐
│  Backend (FastAPI)         :8000         │
│  /predict  /history  /stats             │
│  model_handler.py (TFLite Inference)    │
│  database.py (SQLite)                   │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Model AI                               │
│  model_tbs.tflite (MobileNetV2)         │
│  labels.txt                             │
└─────────────────────────────────────────┘
```

---

## 📂 Struktur Folder

```
tbs-deteksi/
├── app/                              # Android native (Kotlin + Compose)
│   ├── src/main/
│   │   ├── AndroidManifest.xml
│   │   ├── java/com/tbsdeteksi/
│   │   │   ├── MainActivity.kt
│   │   │   └── ui/theme/
│   │   ├── res/values/
│   │   ├── res/xml/
│   │   └── assets/
│   │       └── index.html          # React app bundle
│   ├── build.gradle.kts
│   ├── proguard-rules.pro
│   └── .gitignore
├── backend/
│   ├── main.py                    # FastAPI server (5 endpoint)
│   ├── model_handler.py           # Load TFLite, preprocess 224x224, predict
│   ├── database.py                # SQLite: save history + query stats
│   ├── generate_dummy_model.py    # Buat dummy model untuk testing UI
│   ├── requirements.txt           # Python dependencies
│   ├── uploads/                   # Folder penyimpanan gambar hasil deteksi
│   └── model_output/
│       └── labels.txt             # 5 label kelas (mentah s/d busuk)
├── frontend/
│   ├── index.html                 # Entry HTML
│   ├── package.json               # Node dependencies
│   ├── vite.config.js             # Vite config + proxy ke backend
│   └── src/
│       ├── main.jsx               # ReactDOM entry
│       ├── App.jsx                # Layout utama + tab navigasi
│       ├── App.css                # Full styling (mobile-first)
│       └── components/
│           ├── DeteksiBaru.jsx    # Upload galeri + kamera getUserMedia
│           ├── HasilDeteksi.jsx   # Kartu hasil + score bars + rekomendasi
│           ├── Riwayat.jsx        # List history deteksi dari API
│           └── Dashboard.jsx      # PieChart + BarChart (Recharts)
├── build.gradle.kts
├── settings.gradle.kts
├── gradle.properties
├── gradlew / gradlew.bat
├── gradle/libs.versions.toml
├── run.ps1                        # Build & install APK
├── .vscode/tasks.json             # Ctrl+Shift+B shortcuts
└── README.md
```

---

## 🚀 Panduan Menjalankan

**Syarat:** Python 3.10+ | Node.js 18+ | npm

### 🔧 BAGIAN 1 — Backend (FastAPI + Model AI)

Buka terminal di folder backend:

```powershell
cd backend
```

**Langkah 1: Install dependency Python**
```powershell
pip install -r requirements.txt
```
Install: `fastapi`, `uvicorn`, `tensorflow`, `numpy`, `pillow`, `python-multipart`

**Langkah 2: Siapkan model AI**

✅ **Opsi A — Sudah punya model hasil training?**
Copy `model_tbs.tflite` dan `labels.txt` dari folder `model_output/` hasil training ke `backend/model_output/`

🔄 **Opsi B — Ingin testing UI dulu (tanpa training)?**
Generate model dummy (random weights, hasil tidak akurat):
```powershell
python generate_dummy_model.py
```

> ⚠️ **Untuk hasil akurat**, training model asli pakai `train_model_tbs.py` yang ada di folder project utama. Butuh dataset 5 folder: `mentah/`, `kurang_matang/`, `matang/`, `terlalu_matang/`, `busuk/`

**Langkah 3: Jalankan server**
```powershell
python main.py
```

Output:
```
Labels loaded: ['mentah', 'kurang_matang', 'matang', 'terlalu_matang', 'busuk']
TFLite model loaded: ...\model_tbs.tflite
Model ready!
INFO:     Uvicorn running on http://0.0.0.0:8000
```

✅ **API tersedia** — buka `http://localhost:8000/docs` untuk Swagger UI


| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/` | GET | Cek status server |
| `/predict` | POST | Upload gambar → hasil klasifikasi + rekomendasi |
| `/history` | GET | Riwayat deteksi (50 terakhir) |
| `/stats` | GET | Statistik dashboard (per kategori + tren harian) |
| `/kelas-info` | GET | Info detail 5 kategori + rekomendasi |
| `/uploads/` | Static | Akses foto hasil deteksi |

---

### 🎨 BAGIAN 2 — Frontend (React + Vite)

Buka terminal baru di folder frontend:

```powershell
cd frontend
```

**Langkah 1: Install dependency Node.js**
```powershell
npm install
```
Install: `react`, `react-router-dom`, `recharts`, `vite`

**Langkah 2: Jalankan dev server**
```powershell
npm run dev
```

Output:
```
VITE v5.x.x  ready in xxx ms
➜  Local:   http://localhost:3000/
```

✅ Buka browser ke `http://localhost:3000`

---

### 📱 Menggunakan Aplikasi

| Tab | Fungsi |
|-----|--------|
| 📸 **Deteksi Baru** | Upload dari galeri atau ambil foto dengan kamera. Klik **Deteksi Kematangan** untuk proses |
| 📋 **Riwayat** | Lihat semua history deteksi lengkap dengan timestamp, confidence, dan rekomendasi |
| 📊 **Dashboard** | Pie chart distribusi kematangan + bar chart tren harian (7 hari terakhir) |

**Alur deteksi:**
1. Tab Deteksi Baru → ambil/upload foto TBS
2. Klik "Deteksi Kematangan" → loading spinner
3. Muncul hasil: kategori (warna indikator), confidence %, score bars per kelas, rekomendasi
4. Hasil otomatis tersimpan ke riwayat (SQLite)
5. Dashboard terupdate realtime

---

### 🏃 Ringkasan Flow

```
Terminal 1:  cd backend   → pip install -r requirements.txt
                            → python generate_dummy_model.py   (opsional)
                            → python main.py                   (port 8000)

Terminal 2:  cd frontend  → npm install
                            → npm run dev                      (port 3000)

Browser:     http://localhost:3000
```

---

## 🎯 Kategori Klasifikasi

| No | Kelas | Nama EN | Warna | Tindakan |
|----|-------|---------|-------|----------|
| 1 | Mentah | Unripe | 🔴 `#DC2626` | Tidak layak panen. Tunggu 7-10 hari lagi |
| 2 | Kurang Matang | Underripe | 🟡 `#D97706` | Belum optimal. Tunggu 3-5 hari lagi |
| 3 | **Matang Optimal** | **Ripe** | 🟢 `#16A34A` | **Layak panen! Kematangan optimal** |
| 4 | Terlalu Matang | Overripe | 🟠 `#EA580C` | Terlalu matang. Segera panen/reject |
| 5 | Busuk/Abnormal | Rotten | 🟣 `#6B21A8` | **Tolak!** Tidak layak olah |

---

## 🛠️ Tech Stack

**Backend:** Python 3.13 · FastAPI · TensorFlow Lite · SQLite · Pillow · Uvicorn

**Frontend:** React 18 · Vite · Recharts · CSS3 (Mobile-first, no CSS framework)

**Android:** Kotlin · Jetpack Compose · WebView · Gradle 8.7

**Model AI:** MobileNetV2 (Transfer Learning) · TFLite (quantized) · Input 224×224 RGB

**Training:** MobileNetV2 pre-trained · ImageNet weights · 2.4M params (164K trainable) · Data Augmentation

---

## 📊 Training Model AI

### Dataset Options

**Opsi A: Mendeley (Classification, Recommended)**
```
https://data.mendeley.com/datasets/424y96m6sw/1
```
- 4.728 gambar resolusi tinggi
- 5 kelas: Immature → Mentah, Partially Ripe → Kurang Matang, Fully Ripe → Matang, Overripe → Terlalu Matang, Decayed → Busuk
- Sudah format classification (folder per kelas)

**Opsi B: Roboflow YOLO → Classification**
```
https://universe.roboflow.com/achmad-fahri-x6r0k/oil-palm-fruit-ripeness-7r3zr
```
- 4.160 gambar + bounding box
- Download format YOLOv8, convert via `convert_yolo_to_classification.py`

**Opsi C: Synthetic (Testing Pipeline)**
```powershell
python generate_synthetic_dataset.py  # 250 images, pattern-based
```

### Training Steps

```powershell
# 1. Download dataset (Opsi A)
#    Kunjungi link Mendeley, download ZIP, extract

# 2. Organize ke struktur 5 folder:
#    dataset/mentah/  dataset/kurang_matang/  dataset/matang/
#    dataset/terlalu_matang/  dataset/busuk/

# 3. Install dependencies
pip install -r requirements-training.txt

# 4. Train (10-30 menit)
python train_model_tbs.py

# 5. Output model:
#    backend/model_output/model_tbs.tflite (2.7 MB, Android)
#    backend/model_output/model_tbs_final.keras (11 MB, Python)
#    backend/model_output/labels.txt
```

### YOLO → Classification Conversion

```powershell
# Download Roboflow dataset as YOLOv8 → extract ke raw_data/
python convert_yolo_to_classification.py --input raw_data --output dataset --crop
```

### Expected Results

| Dataset Size | Training Time | Expected Accuracy |
|--------------|---------------|-------------------|
| 250 img (synthetic) | 15 min | ~100% (synthetic) |
| 500-1000 img | 15-20 min | 80-90% |
| 1000+ img | 20-30 min | 90-95% |

---

## ⚡ Catatan Penting

- **Model sintetis (bawaan)** bisa dipakai untuk testing UI, tapi hasil deteksi random. Training dengan dataset asli untuk akurasi production.
- **Kamera hanya jalan di HTTPS/localhost** — browser blokir `getUserMedia` di plain HTTP selain localhost
- **Port bisa diganti**: backend di `main.py` baris terakhir, frontend di `vite.config.js`
- **GPS opsional**: API sudah support `latitude`/`longitude` params. Frontend bisa tambah `navigator.geolocation` di `DeteksiBaru.jsx`
- **VSCode Launch Config**: Buat file `.vscode/launch.json` untuk run training via F5 (lihat `QUICKSTART.md`)

---

## 📄 Lisensi

Proyek ini dibuat untuk keperluan edukasi dan riset.

---

**🌴 Kelapa Sawit Indonesia Maju!**

