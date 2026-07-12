# AGENTS.md — TBS Deteksi Kelapa Sawit

Monorepo: Android WebView + React frontend + FastAPI backend for palm oil ripeness detection.

## Build Commands

**Full build & install APK** (recommended):
```powershell
.\run.ps1
```

**Partial builds:**
```powershell
npm run build              # frontend only (from frontend/)
.\gradlew.bat assembleDebug  # Gradle only (requires frontend dist/ already in assets/)
.\run.ps1 -Reinstall       # Install APK only (skip build)
.\run.ps1 -SkipBuild       # Gradle only (skip npm build)
```

**Order matters**: React build → copy dist/ to assets/ → Gradle build → ADB install.

## Architecture

- **Android**: `app/` — Jetpack Compose + WebView (loads `file:///android_asset/index.html`)
- **Frontend**: `frontend/` — React 18 + Vite (port 3000 in dev, proxies /api to backend)
- **Backend**: `backend/` — FastAPI (port 8000, runs `/api/predict`, `/api/history`, `/api/stats`)
- **Model**: `backend/model_output/` — TFLite or Keras + labels.txt

## Frontend Build Output

React build output (`frontend/dist/`) **must** be copied to `app/src/main/assets/` before Gradle build.

`run.ps1` does this automatically. Manual copy:
```powershell
Copy-Item frontend\dist\* app\src\main\assets\ -Recurse -Force
```

## Model & Labels

- **TFLite path**: `backend/model_output/model_tbs.tflite` (preferred)
- **Keras fallback**: `backend/model_output/model_tbs_final.keras` (if TFLite not found)
- **Labels**: `backend/model_output/labels.txt` (one per line; fallback: mentah, kurang_matang, matang, terlalu_matang, busuk)

If neither model exists, generate dummy for testing:
```powershell
cd backend
python generate_dummy_model.py
```

## Database

- **Path**: `backend/deteksi_tbs.db` (SQLite)
- **Table**: `history` — id, timestamp, kelas, confidence, rekomendasi, all_scores (string), image_path, latitude, longitude
- Auto-created on first `main.py` startup

## Android APK

- **Package ID**: `com.tbsdeteksi.kelapa.sawit`
- **Debug APK**: `app-debug.apk` (auto-signed with debug.keystore)
- **Release APK**: requires env vars `KEYSTORE_PATH`, `STORE_PASSWORD`, `KEY_PASSWORD`
- **Output**: `app/build/outputs/apk/debug/app-debug.apk`
- **Permissions**: CAMERA, ACCESS_FINE_LOCATION (requested at app startup)

## Dev Mode

**Terminal 1 (Backend)**:
```powershell
cd backend
pip install -r requirements.txt
python main.py
# http://localhost:8000/docs for Swagger UI
```

**Terminal 2 (Frontend)**:
```powershell
cd frontend
npm install
npm run dev
# http://localhost:3000 (proxies /api to http://localhost:8000)
```

Backend and frontend run independently in dev; Vite proxies API calls.

## VSCode Tasks (Ctrl+Shift+B)

- **Build APK (Gradle)** — `run.ps1 -SkipBuild` (default)
- **Build & Install APK** — `run.ps1`
- **Build React Only** — `npm run build` (frontend/)
- **Reinstall APK** — `run.ps1 -Reinstall`

## Code Structure

```
frontend/src/
├── App.jsx           # Tabs: deteksi, riwayat, dashboard
├── App.css           # Mobile-first, no CSS framework
├── components/
│   ├── DeteksiBaru.jsx      # Upload gallery + camera (getUserMedia)
│   ├── HasilDeteksi.jsx     # Results + confidence bars
│   ├── Riwayat.jsx          # History list from /api/history
│   └── Dashboard.jsx        # Pie + bar charts (Recharts)
└── ondevice/
    └── model_loader.js      # TF.js + TFLite backend (optional)

backend/
├── main.py            # FastAPI app, 5 endpoints + static serving
├── model_handler.py   # TFLite/Keras loader, preprocess, predict
├── database.py        # SQLite: init, save, query history + stats
└── model_output/
    ├── model_tbs.tflite
    ├── model_tbs_final.keras (fallback)
    └── labels.txt

app/src/main/
├── java/com/tbsdeteksi/
│   └── MainActivity.kt  # WebView wrapper (loads assets/index.html)
└── assets/
    └── index.html       # (Generated from frontend/dist/)
```

## Key Classes & Methods

- **TBSClassifier** (model_handler.py): `predict(image)` returns {kelas_pred, confidence, all_scores, rekomendasi, warna, ...}
- **Database** (database.py): `save_detection(...)`, `get_all_history(limit)`, `get_stats()`
- **API endpoints** (main.py): `/api/predict`, `/api/history`, `/api/stats`, `/api/kelas-info`

## Common Issues

- **"frontend/dist/ not found"** → Run `npm run build` in frontend/ first
- **"Model not found"** → Generate dummy or provide model_tbs.tflite + labels.txt
- **"Port 8000 in use"** → Change in backend/main.py line 136; update vite.config.js proxy
- **"ADB: device not found"** → Connect via USB or use `run.ps1 -IPAddress "192.168.1.100:5555"` for wireless
- **"Cannot read property 'getUserMedia'"** → App only loads from HTTPS or localhost; browser blocks plain HTTP
