# 🌴 TBS Deteksi Kelapa Sawit

Aplikasi web **deteksi tingkat kematangan Tandan Buah Segar (TBS) kelapa sawit** menggunakan AI Computer Vision dengan TensorFlow Lite.

---

## ✨ Fitur

- 📸 **Upload foto** atau **ambil langsung dari kamera** (realtime)
- 🔍 **Klasifikasi 5 kategori**: Mentah, Kurang Matang, Matang, Terlalu Matang, Busuk
- ✅ **Confidence score (%)** tiap kategori + progress bar visual
- 💬 **Rekomendasi tindakan** per kategori (Layak panen / Tunggu / Tolak)
- 📋 **Riwayat deteksi** lengkap dengan timestamp (SQLite)
- 📊 **Dashboard statistik** — Pie chart distribusi + Bar chart tren harian (Recharts)
- 📱 **Mobile-friendly UI** — Tombol besar, kontras tinggi, akses kamera via browser

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

**Model AI:** MobileNetV2 (Transfer Learning) · TFLite (quantized) · Input 224×224 RGB

---

## ⚡ Catatan Penting

- **Model asli belum ada** — harus training dulu dengan `train_model_tbs.py` (butuh dataset foto TBS 5 kategori), atau pakai `generate_dummy_model.py` untuk testing UI
- **Kamera hanya jalan di HTTPS/localhost** — browser blokir `getUserMedia` di plain HTTP selain localhost
- **Port bisa diganti**: backend di `main.py` baris terakhir, frontend di `vite.config.js`
- **GPS opsional**: API sudah support `latitude`/`longitude` params. Frontend bisa tambah `navigator.geolocation` di `DeteksiBaru.jsx`

---

## 📄 Lisensi

Proyek ini dibuat untuk keperluan edukasi dan riset.

---

**🌴 Kelapa Sawit Indonesia Maju!**

