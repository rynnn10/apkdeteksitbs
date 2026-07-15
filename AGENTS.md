# AGENTS.md — TBS Deteksi Kelapa Sawit

Monorepo: Android WebView + React frontend + FastAPI backend for palm oil ripeness detection.

## Agent Guidance

- This repo is a hybrid Android app built from a React web frontend and a Python backend. Most UI changes happen in `frontend/src/`; Android packaging is in `app/`; API logic is in `backend/`.
- Use `.
un.ps1` for the main build flow. For local web-only work, run the backend from `backend/` and the frontend from `frontend/`.
- Do not edit generated frontend assets under `frontend/dist/` or `app/src/main/assets` directly; rebuild from source instead.
- Backend endpoints are defined in `backend/main.py`; model loading and inference live in `backend/model_handler.py`.
- Training and model workflow is separate from app packaging; use root training scripts only when requested.
- There is no `.github/copilot-instructions.md` in this repo; `AGENTS.md` is the primary AI guidance file.

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

- **Server detection**: `backend/model_output/yolov8_tbs.pt` (YOLOv8) — preferred, returns bounding boxes per TBS
- **Server classification fallback**: `backend/model_output/model_tbs.tflite` or `model_tbs_final.keras` (single label per image)
- **On-device (offline) detection**: `frontend/public/model_tfjs_yolo/` — YOLOv8 exported to TF.js graph model (`nms=True`), same weights as `yolov8_tbs.pt`. **Not present by default** — export it on Colab (see "Export YOLO to TF.js" below) and drop the output here. Without it, on-device mode falls back to the single-label classifier below.
- **On-device (offline) classification fallback**: `frontend/public/model_tfjs/` — Keras MobileNetV2 exported to TF.js layers model, 1 label per photo.
- **Labels**: `backend/model_output/labels.txt` (Roboflow class names — mapped to the 5 internal keys via `ROBOFLOW_TO_INTERNAL` in both `backend/model_handler.py` and `frontend/src/ondevice/model_loader.js`; keep both in sync)
- **Dummy (test UI)**: `cd backend; python generate_dummy_model.py`
- **Train YOLOv8 on Colab**: `train_yolov8_colab.py` — copies cells into Google Colab, outputs `.pt` + `.tflite`

### Export YOLO to TF.js (for offline on-device detection)

No retraining needed if `yolov8_tbs.pt` already performs well server-side — just re-export it. Must run on Colab (or any fresh Python env); the project's local `.venv` has a `numpy`/`tensorflowjs` version conflict that breaks the converter.

```python
# Colab cell
!pip install -q ultralytics tensorflowjs
from ultralytics import YOLO
model = YOLO("yolov8_tbs.pt")  # upload your trained weights first
model.export(format="saved_model", imgsz=640, nms=True)  # -> yolov8_tbs_saved_model/

!tensorflowjs_converter --input_format=tf_saved_model --output_format=tfjs_graph_model \
  yolov8_tbs_saved_model yolov8_tbs_web

!zip -r yolov8_tbs_web.zip yolov8_tbs_web
from google.colab import files
files.download("yolov8_tbs_web.zip")
```

Unzip and copy the contents into `frontend/public/model_tfjs_yolo/` (so it contains `model.json` + `.bin` shard(s) directly, no nested folder), then `npm run build` + copy `dist/` to `app/src/main/assets/` as usual. If `yolov8_tbs.pt` is ever retrained with a different class set, update `YOLO_LABELS` in `frontend/src/ondevice/model_loader.js` to match the new `labels.txt` order.

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
