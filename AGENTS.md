# AGENTS.md — TBS Deteksi Kelapa Sawit

Monorepo: Android WebView + React frontend + FastAPI backend for palm oil ripeness detection.

## Build Commands

**Full build & install APK** (interactive, auto-detects devices):
```powershell
.\run.ps1
```

**Manual build steps (order matters):**
```powershell
npm run build                                    # frontend/
Copy-Item frontend\dist\* app\src\main\assets\ -Recurse -Force
.\gradlew.bat assembleDebug                      # outputs app/build/outputs/apk/debug/app-debug.apk
adb install -r app\build\outputs\apk\debug\app-debug.apk
```

**`run.ps1` accepts**: `-DeviceId "192.168.1.100:5555"` (wireless) or `"usb"` (USB). No `-SkipBuild`/`-Reinstall` flags exist.

VSCode `Ctrl+Shift+B` tasks pass unrecognized flags to `run.ps1` — they are ignored and the full pipeline runs.

## Architecture

- **Android**: `app/` — Jetpack Compose + WebView (loads `file:///android_asset/index.html`)
- **Frontend**: `frontend/` — React 18 + Vite (port 3000 in dev, proxies `/api` and `/uploads` to localhost:8000)
- **Backend**: `backend/` — FastAPI (port 8000, endpoints: `/api/predict`, `/api/history`, `/api/stats`, `/api/kelas-info`, `/api/version`)
- **APK back button**: Konfirmasi keluar via `OnBackPressedCallback`
- **Native YOLO**: `YoloDetector.kt` + JS bridge (`NativeDetector`) — offline TFLite inference di APK
- **Model file APK**: `app/src/main/assets/best.tflite` (YOLOv8 TFLite untuk native)
- **Model**: `backend/model_output/` — YOLOv8 `.pt` (detection) or TFLite/Keras fallback (classification)

## Dev Mode

Two terminals:
```powershell
# Terminal 1 — Backend
cd backend; pip install -r requirements.txt
python main.py              # prod mode (serves frontend from ../frontend/dist/)
python main.py --dev        # API only, frontend via npm run dev (Vite)

# Terminal 2 — Frontend
cd frontend; npm install
npm run dev                 # http://localhost:3000
```

Backend and frontend are independent in dev mode; Vite proxies API calls.

## Model

- **Detection**: `backend/model_output/yolov8_tbs.pt` (YOLOv8) — preferred, returns bounding boxes per TBS
- **Classification fallback**: `backend/model_output/model_tbs.tflite` or `model_tbs_final.keras` (single label per image)
- **Labels**: `backend/model_output/labels.txt` (mentah, kurang_matang, matang, terlalu_matang, busuk)
- **Dummy (test UI)**: `cd backend; python generate_dummy_model.py`
- **Train YOLOv8 on Colab**: `train_yolov8_colab.py` — copies cells into Google Colab, outputs `.pt` + `.tflite`

## Database

- `backend/deteksi_tbs.db` (SQLite, auto-created on first startup)
- Table `history`: id, timestamp, kelas, confidence, rekomendasi, all_scores, image_path, latitude, longitude

## Android APK

- **Package**: `com.tbsdeteksi.kelapa.sawit`, compileSdk=36, minSdk=24
- **Debug**: signed with `debug.keystore` (password: android)
- **Release**: requires env vars `KEYSTORE_PATH`, `STORE_PASSWORD`, `KEY_PASSWORD`
- **Permissions**: CAMERA, ACCESS_FINE_LOCATION

## Training

Multiple training script variants at project root. All produce output in `backend/model_output/`:
- `train_model_tbs.py` — MobileNetV2 transfer learning (baseline, 2-stage: head freeze → fine-tune)
- `train_mobilenetv2_improved.py` — improved MobileNetV2 variant
- `train_efficientnet.py` — EfficientNet variant
- `train_efficientnet_v2.py` — EfficientNetV2 variant
- `train_ordinal.py` — ordinal regression approach

**Quick start:**
```powershell
pip install -r requirements-training.txt
python train_model_tbs.py                              # expects dataset/ with 5 class subfolders
python generate_synthetic_dataset.py                   # or generate synthetic test data
```

**TF.js conversion (on-device inference):** `python convert_to_tfjs.py` or `convert_effnet_tfjs.py`

**YOLOv8 object detection training (Colab):** `train_yolov8_colab.py` — copy cells to Colab. Requires Roboflow API key. Output `yolov8_tbs.pt` goes in `backend/model_output/`.

## Code Structure

```
frontend/src/
└── components/
    ├── DeteksiBaru.jsx   # Upload gallery + camera (getUserMedia)
    ├── HasilDeteksi.jsx  # Results + confidence bars + recommendation
    ├── Riwayat.jsx       # History list from /api/history
    └── Dashboard.jsx     # Pie + bar charts (Recharts)

backend/
├── main.py              # FastAPI, 6 endpoints + static SPA serving + /api/version
├── model_handler.py     # TBSDetector (YOLOv8) + TBSClassifier (TFLite/Keras fallback)
└── database.py          # SQLite: save_detection(), get_all_history(), get_stats()

app/src/main/java/com/tbsdeteksi/
└── MainActivity.kt      # WebView wrapper, loads assets/index.html
```

## Common Issues

- **"frontend/dist/ not found"** → Run `npm run build` in frontend/ first
- **"Model not found"** → For detection: train YOLOv8 on Colab via `train_yolov8_colab.py`, place `.pt` in `backend/model_output/`. For classification: generate dummy (`python backend/generate_dummy_model.py`)
- **Port 8000 in use** → Change in `backend/main.py` last line; update `frontend/vite.config.js` proxy
- **ADB: device not found** → `run.ps1 -DeviceId "192.168.1.100:5555"` for wireless, or `"usb"` for USB
- **getUserMedia fails** → HTTPS or localhost only; browser blocks plain HTTP
