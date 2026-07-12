"""
FastAPI backend untuk deteksi TBS kelapa sawit.
Endpoints:
  POST /predict          - klasifikasi gambar
  GET  /history          - riwayat deteksi
  GET  /stats            - dashboard statistik
  GET  /kelas-info       - info semua kelas
"""
import os
import json
import shutil
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image
import io

from model_handler import get_classifier
from database import init_db, save_detection, get_all_history, get_stats

app = FastAPI(title="TBS Deteksi API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.on_event("startup")
def startup():
    init_db()
    # warm up model
    try:
        get_classifier()
        print("Model ready!")
    except Exception as e:
        print(f"WARNING: Model not loaded: {e}")

@app.get("/")
def root():
    return {"app": "TBS Deteksi Kelapa Sawit", "status": "running"}

@app.get("/kelas-info")
def kelas_info():
    from model_handler import KELAS_INFO
    return KELAS_INFO

@app.post("/predict")
async def predict(
    file: UploadFile = File(...),
    latitude: float = Form(None),
    longitude: float = Form(None),
):
    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert("RGB")

    classifier = get_classifier()
    result = classifier.predict(image)

    # Simpan gambar
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    img_filename = f"{ts}_{result['kelas_pred']}.jpg"
    img_path = os.path.join(UPLOAD_DIR, img_filename)
    image.save(img_path, "JPEG")

    # Simpan ke DB
    det_id = save_detection(
        kelas=result["kelas_pred"],
        confidence=result["confidence"],
        rekomendasi=result["rekomendasi"],
        all_scores=result["all_scores"],
        image_path=img_path,
        latitude=latitude,
        longitude=longitude,
    )

    result["id"] = det_id
    result["image_url"] = f"/uploads/{img_filename}"
    return result

@app.get("/history")
def history(limit: int = 50):
    return get_all_history(limit)

@app.get("/stats")
def stats():
    return get_stats()


# Serve uploaded images
from fastapi.staticfiles import StaticFiles
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
