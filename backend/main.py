"""
TBS Deteksi Kelapa Sawit — Fullstack App
=========================================
  API: /api/predict | /api/history | /api/stats | /api/kelas-info | /api/version
  SPA: / (frontend dari ../frontend/dist/)
  Gambar: /uploads/

Now with YOLOv8 object detection (multiple TBS per image) + confidence thresholds for non-TBS rejection.
Updated: 2026-07-15 14:10 WIB | v2.2.4
"""
import os
import sys
import json
import socket
import subprocess
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
import io

from model_handler import get_detector
from database import init_db, save_detection, get_all_history, get_stats

APP_VERSION = "2.2.4"
BUILD_DATE = "2026-07-15 14:10 WIB"

DEV_MODE = "--dev" in sys.argv

app = FastAPI(title="TBS Deteksi Kelapa Sawit", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend", "dist")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.on_event("startup")
def startup():
    init_db()
    try:
        get_detector()
        print("[OK] Detector loaded")
    except Exception as e:
        print(f"[WARN] Detector not loaded: {e}")

    if DEV_MODE:
        print("[DEV] Running in dev mode")
    elif os.path.isdir(FRONTEND_DIR):
        print(f"[OK] Frontend static: {os.path.abspath(FRONTEND_DIR)}")
    else:
        print(f"[WARN] No frontend dist/ — run npm run build")


# ── API Endpoints ────────────────────────────────────────

@app.get("/api/kelas-info")
def kelas_info():
    from model_handler import KELAS_INFO
    return KELAS_INFO

@app.get("/api/version")
def version():
    return {"app": "TBS Deteksi Kelapa Sawit", "version": APP_VERSION, "build_date": BUILD_DATE}

@app.get("/api")
def api_root():
    return {"app": "TBS Deteksi Kelapa Sawit", "version": APP_VERSION, "mode": "dev" if DEV_MODE else "prod"}

@app.post("/api/predict")
async def predict(
    file: UploadFile = File(...),
    latitude: float = Form(None),
    longitude: float = Form(None),
):
    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert("RGB")

    detector = get_detector()
    detections, img_w, img_h = detector.predict(image)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    image_url = None
    if detections:
        for det in detections:
            img_filename = f"{ts}_{det['kelas_pred']}.jpg"
            img_path = os.path.join(UPLOAD_DIR, img_filename)
            image.save(img_path, "JPEG")
            det["image_url"] = f"/uploads/{img_filename}"
        det_id = save_detection(
            kelas="|".join(d["kelas_pred"] for d in detections),
            confidence=max(d["confidence"] for d in detections),
            rekomendasi="; ".join(d["rekomendasi"] for d in detections),
            all_scores={"detections": detections},
            image_path=img_path,
            latitude=latitude, longitude=longitude,
        )
        image_status = "tbs"
        message = None
    else:
        det_id = save_detection(
            kelas="tidak_dikenal",
            confidence=0.0,
            rekomendasi="Gambar tidak dikenali sebagai TBS. Pastikan foto jelas dan objek yang dicari terlihat.",
            all_scores={"detections": []},
            image_path=None,
            latitude=latitude, longitude=longitude,
        )
        image_status = "unknown"
        message = (
            "Gambar tidak dikenali sebagai TBS. Pastikan foto berisi tandan buah segar, "
            "pencahayaan cukup, dan objek TBS terlihat jelas dalam frame."
        )

    no_detection = len(detections) == 0
    return {
        "detections": detections,
        "image_width": img_w,
        "image_height": img_h,
        "detection_count": len(detections),
        "no_detection": no_detection,
        "image_status": image_status,
        "message": message,
        "id": det_id,
    }

@app.get("/api/history")
def history(limit: int = 50):
    return get_all_history(limit)

@app.get("/api/stats")
def stats():
    return get_stats()


# ── Static file serving ─────────────────────────────────

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

if not DEV_MODE and os.path.isdir(FRONTEND_DIR):
    from fastapi.responses import HTMLResponse

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    if os.path.isdir(os.path.join(FRONTEND_DIR, "assets")):
        app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")


def _find_free_port(start_port=8000, max_attempts=10):
    """Find first available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    return None


def _kill_port(port):
    """Kill process listening on given port (Windows)."""
    try:
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            shell=True, capture_output=True, text=True
        )
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                parts = line.strip().split()
                if len(parts) >= 5 and 'LISTENING' in line:
                    pid = parts[-1]
                    subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
                    print(f"[OK] Killed process PID {pid} on port {port}")
                    return True
    except Exception as e:
        print(f"[WARN] Could not kill port {port}: {e}")
    return False


if __name__ == "__main__":
    import uvicorn
    
    # Auto-free port 8000 if in use
    PORT = 8000
    if not _find_free_port(PORT, 1):
        print(f"[WARN] Port {PORT} in use, attempting to kill...")
        _kill_port(PORT)
        import time
        time.sleep(1)
        if not _find_free_port(PORT, 1):
            # Try fallback port
            fallback = _find_free_port(PORT + 1, 10)
            if fallback:
                print(f"[INFO] Using fallback port {fallback}")
                PORT = fallback
            else:
                print("[ERROR] No available ports found!")
                sys.exit(1)
    
    print(f"\n{'='*60}")
    print("  TBS Deteksi Kelapa Sawit")
    print(f"  v{APP_VERSION} | {BUILD_DATE}")
    print(f"  Mode: {'DEV (API only)' if DEV_MODE else 'PROD'}")
    print(f"  URL:  http://localhost:{PORT}")
    print(f"{'='*60}\n")
    uvicorn.run(app, host="0.0.0.0", port=PORT)