"""
TBS Deteksi Kelapa Sawit — Fullstack App
=========================================
  API: /api/predict | /api/history | /api/stats | /api/kelas-info
  SPA: / (frontend dari ../frontend/dist/)
  Gambar: /uploads/

Deployment mode: python main.py          (prod — single server, serve frontend)
Dev mode:        python main.py --dev     (API only, frontend via npm run dev)
"""
import os
import sys
import json
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
import io

from model_handler import get_classifier
from database import init_db, save_detection, get_all_history, get_stats

# --dev flag: API only, no frontend serving
DEV_MODE = "--dev" in sys.argv

app = FastAPI(title="TBS Deteksi Kelapa Sawit", version="1.0.0")

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
        get_classifier()
        print("[OK] Model loaded")
    except Exception as e:
        print(f"[WARN] Model not loaded: {e}")

    if DEV_MODE:
        print("[DEV] Running in dev mode — frontend served separately (npm run dev)")
    elif os.path.isdir(FRONTEND_DIR):
        print(f"[OK] Frontend static: {os.path.abspath(FRONTEND_DIR)}")
    else:
        print(f"[WARN] No frontend dist/ — run build_frontend.ps1 or npm run build")


# ── API Endpoints ────────────────────────────────────────

@app.get("/api/kelas-info")
def kelas_info():
    from model_handler import KELAS_INFO
    return KELAS_INFO

@app.get("/api")
def api_root():
    return {"app": "TBS Deteksi Kelapa Sawit", "mode": "dev" if DEV_MODE else "prod"}

@app.post("/api/predict")
async def predict(
    file: UploadFile = File(...),
    latitude: float = Form(None),
    longitude: float = Form(None),
):
    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert("RGB")

    classifier = get_classifier()
    result = classifier.predict(image)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    img_filename = f"{ts}_{result['kelas_pred']}.jpg"
    img_path = os.path.join(UPLOAD_DIR, img_filename)
    image.save(img_path, "JPEG")

    det_id = save_detection(
        kelas=result["kelas_pred"],
        confidence=result["confidence"],
        rekomendasi=result["rekomendasi"],
        all_scores=result["all_scores"],
        image_path=img_path,
        latitude=latitude, longitude=longitude,
    )

    result["id"] = det_id
    result["image_url"] = f"/uploads/{img_filename}"
    return result

@app.get("/api/history")
def history(limit: int = 50):
    return get_all_history(limit)

@app.get("/api/stats")
def stats():
    return get_stats()


# ── Static file serving ─────────────────────────────────

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# SPA fallback: serve frontend dist/ jika tersedia
if not DEV_MODE and os.path.isdir(FRONTEND_DIR):
    from fastapi.responses import HTMLResponse

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """SPA fallback — all non-API routes → index.html"""
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    # Mount assets directory
    if os.path.isdir(os.path.join(FRONTEND_DIR, "assets")):
        app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")


if __name__ == "__main__":
    import uvicorn
    print(f"\n{'='*60}")
    print("  🌴 TBS Deteksi Kelapa Sawit")
    print(f"  Mode: {'DEV (API only)' if DEV_MODE else 'PROD (fullstack)'}")
    print(f"  URL:  http://localhost:8000")
    print(f"{'='*60}\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
