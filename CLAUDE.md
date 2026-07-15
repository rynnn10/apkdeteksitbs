# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`AGENTS.md` also exists in this repo root and is treated as the primary AI guidance file for this project — read it too. This file adds architecture context that isn't obvious from a single file read.

## Commands

**Full build & install APK** (interactive, auto-detects devices):
```powershell
.\run.ps1
.\run.ps1 -DeviceId "192.168.1.100:5555"   # wireless
.\run.ps1 -DeviceId "usb"                  # USB
```
No `-SkipBuild`/`-Reinstall` flags exist — VSCode `Ctrl+Shift+B` tasks pass extra flags but they're ignored and the full pipeline always runs.

**Manual build steps (order matters — frontend must be built and copied before Gradle):**
```powershell
npm run build                                    # frontend/ -> frontend/dist/
Copy-Item frontend\dist\* app\src\main\assets\ -Recurse -Force
.\gradlew.bat assembleDebug                      # -> app/build/outputs/apk/debug/app-debug.apk
adb install -r app\build\outputs\apk\debug\app-debug.apk
```
Release build needs env vars `KEYSTORE_PATH`, `STORE_PASSWORD`, `KEY_PASSWORD`, then `.\gradlew.bat assembleRelease`.

**Dev mode** (backend and frontend run independently, Vite proxies `/api` and `/uploads` to `localhost:8000`):
```powershell
# Terminal 1
cd backend; pip install -r requirements.txt
python main.py --dev        # API only

# Terminal 2
cd frontend; npm install
npm run dev                 # http://localhost:3000
```
`python main.py` (no `--dev`) serves the built frontend from `../frontend/dist/` instead of proxying to Vite — use this to test the actual prod-serving path.

There is no test suite in this repo (no `pytest`/`jest`/`vitest` config or test files) — don't invent test commands.

## Architecture

Three independently runnable tiers glued together at build time, not at runtime:

- **`app/`** — Kotlin/Compose shell. `MainActivity.kt` is a bare `WebView` loading `file:///android_asset/index.html`. It does **not** inject any JS bridge (the old `NativeDetector`/`YoloDetector.kt` bridge was removed in v2.5.0). Its only jobs: camera/location permission requests, file-chooser passthrough for `<input type=file>`, geolocation permission passthrough, and a confirm-to-exit dialog via `OnBackPressedCallback`.
- **`frontend/`** — React 18 + Vite SPA. Gets built to `dist/` and copied verbatim into `app/src/main/assets/`. Never edit `app/src/main/assets/` or `frontend/dist/` directly — they're build output.
- **`backend/`** — FastAPI, single process, serves both the REST API and (in prod mode) the built SPA as static files with a catch-all SPA route.

### The three-mode detection system (the main thing to understand)

The frontend never assumes connectivity. `DeteksiBaru.jsx` picks one of three modes at runtime and persists the user's preference (`forced_mode` in `localStorage`):

- **`server`** — POSTs to `{serverIp}:8000/api/predict` (or same-origin `/api` when not in the Android WebView). Server IP is user-entered and saved to `localStorage` (`server_ip`) because the APK talks to a backend running on the user's laptop over LAN, not a hosted service.
- **`ondevice`** — routed through `frontend/src/ondevice/model_loader.js` → `predictOnDevice()`, which tries three tiers in order:
  1. `predictWithYOLO()` — real multi-box detection via `frontend/public/model_tfjs_yolo/`, a TF.js graph-model export of the same `yolov8_tbs.pt` the server runs (`nms=True` baked into the graph, so no client-side NMS is needed). **This directory is not checked into the repo by default** — see AGENTS.md's "Export YOLO to TF.js" for how to produce it on Colab; until then this tier is silently skipped. Preprocessing letterboxes to 640×640 with Ultralytics' default gray (114,114,114) padding (`letterboxCanvas()` / the pure math in `frontend/src/ondevice/yolo_geometry.js`), matching what `ultralytics` does internally — get this wrong and boxes will be offset. Output rows `[x1,y1,x2,y2,conf,cls]` are filtered at `YOLO_CONF_THRESHOLD` (0.25, mirrors the backend) and class indices are mapped through a duplicated `ROBOFLOW_TO_INTERNAL` (keep in sync with `backend/model_handler.py`'s copy — and with `YOLO_LABELS`' order, which must match `backend/model_output/labels.txt` at export time).
  2. `predictWithTFJS()` — single-label classifier via `frontend/public/model_tfjs/` (MobileNetV2 Keras model → TF.js layers model), used only if tier 1's model directory isn't present or fails to load. Preprocessing mirrors `backend/model_handler.py`'s `TBSClassifier.preprocess()` exactly: plain resize to 224×224 (no letterbox), divide by 255. Returns one classification wrapped as a full-frame `{x1:0,y1:0,x2:1,y2:1}` "detection" so `HasilDeteksi.jsx` renders it the same way as real boxes.
  3. `dummyPredictMulti()` — random output, last resort only if neither model directory loads at all.

  Both real tiers load weights via a custom XHR-based `tf.io.IOHandler` (`fileSystemIOHandler`) instead of `tf.loadLayersModel`/`tf.loadGraphModel`'s default `fetch()`-based loader, because `fetch()` does not work against `file://` origins inside the Android WebView.
- **`offline`** — no model available at all; UI shows a disabled/offline badge.

`detectMode()` in `DeteksiBaru.jsx` runs this priority chain: forced server IP → auto-probe saved IP → same-origin `/api` (browser dev only) → on-device availability → offline. `isAndroidWebView` is detected via `window.location.protocol === "file:"`.

### Backend inference fallback chain

`backend/model_handler.py`'s `TBSDetector` tries, in order: YOLOv8 (`model_output/yolov8_tbs.pt`, multi-box detection) → `TBSClassifier` (TFLite `model_tbs.tflite`, then Keras `model_tbs_final.keras`, single-label). If YOLO loads but finds zero boxes above `YOLO_CONF_THRESHOLD` (0.25), it retries with the classifier as a secondary fallback (must clear `CLASSIFIER_CONF_THRESHOLD` = 60% to count) rather than returning empty immediately. Both paths funnel through `_resolve_kelas()`, which also remaps Roboflow's training-dataset class names (`"TBS mentah"`, `"Janjang kosong"`, etc.) to the app's five internal keys — this mapping matters if you retrain or swap in a new `.pt`/`.tflite`.

`KELAS_INFO` in `model_handler.py` is the single source of truth for label metadata (color, bg color, icon, recommendation text) on the backend side; `frontend/src/ondevice/model_loader.js` duplicates the same maps (`WARNA_MAP`, `REKOMENDASI_MAP`, etc.) for the on-device path — keep both in sync when changing wording/colors/thresholds.

### Frontend detection result shape

Both server and on-device paths return `{ detections: [...], detection_count, image_width, image_height }`, where each detection has `bbox` (normalized 0–1 `{x1,y1,x2,y2}`), `kelas_pred`, `confidence`, `all_scores`, `rekomendasi`, `warna`, `bg_warna`, `icon`. `HasilDeteksi.jsx` renders this uniformly regardless of source. `model_loader.js`'s `normalizeBbox()` clamps/rejects boxes (area > `MAX_BBOX_AREA` = 0.85, or degenerate coords) — a safety net against bad inference output covering the whole frame.

On-device results are additionally persisted to a local-only history in `localStorage` (`local_detection_history_v1`, capped at 50) since they never hit the backend's SQLite `history` table — `Riwayat.jsx`/`Dashboard.jsx` only read from `/api/history` and `/api/stats`, so on-device detections won't appear there.

### Database

`backend/database.py`, SQLite at `backend/deteksi_tbs.db`, auto-created on startup. Single `history` table: `id, timestamp, kelas, confidence, rekomendasi, all_scores (JSON), image_path, latitude, longitude`. Multi-detection results are stored with `kelas` as a `|`-joined string and `all_scores` holding the full `detections` array as JSON — there's no per-detection row, only one row per predict call.

### Training pipeline (separate from the app)

Root-level `train_*.py` scripts (MobileNetV2 baseline, EfficientNet/EfficientNetV2 variants, ordinal regression) and `train_yolov8_colab.py` (cell-by-cell Google Colab script) are independent of the running app — they only matter when producing new files for `backend/model_output/`. `generate_synthetic_dataset.py` and `generate_dummy_model.py` exist to unblock UI testing without a real dataset/model. Don't run these unless explicitly asked to work on training.

### Versioning

App version is duplicated in three places that must be bumped together: `backend/main.py` (`APP_VERSION`/`BUILD_DATE`), `frontend/src/App.jsx` (footer text + file header comment), `app/build.gradle.kts` (`versionCode`/`versionName`). There's no single source of truth — check all three when cutting a release.
