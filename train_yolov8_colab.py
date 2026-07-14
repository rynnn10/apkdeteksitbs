"""
YOLOv8 Training for TBS Object Detection — Google Colab
========================================================
Copy each CELL block into a Colab cell and run sequentially.

Output: best.pt (weights) + best.tflite (for Android)
Place best.pt in backend/model_output/yolov8_tbs.pt

Updated: 2026-07-14 15:30 UTC | v2.0.0
"""

# ============================================================
# CELL 1: Install dependencies
# ============================================================
!pip install ultralytics roboflow tensorflowjs -q

# ============================================================
# CELL 2: Download dataset from Roboflow
# (Get free API key: https://universe.roboflow.com — sign up → API keys)
# ============================================================
from roboflow import Roboflow

API_KEY = ""  # <-- PASTE YOUR ROBOFLOW API KEY HERE
if not API_KEY:
    API_KEY = input("Paste Roboflow API key: ")

rf = Roboflow(api_key=API_KEY)
project = rf.workspace("achmad-fahri-x6r0k").project("oil-palm-fruit-ripeness-7r3zr")
dataset = project.version(1).download("yolov8")

# ============================================================
# CELL 3: Inspect dataset structure
# ============================================================
import os, yaml

data_yaml = os.path.join(dataset.location, "data.yaml")
data_dir = os.path.dirname(data_yaml)

with open(data_yaml) as f:
    cfg = yaml.safe_load(f)

# Resolve relative paths from data.yaml directory
train_dir = os.path.normpath(os.path.join(data_dir, cfg["train"]))
val_dir = os.path.normpath(os.path.join(data_dir, cfg["val"]))

print("Classes:", cfg["names"])
print("Train path:", train_dir)
print("Val path:", val_dir)

# ============================================================
# CELL 4: Train YOLOv8
# epochs=50 is good for 4k images. Reduce to 20 for quick test.
# ============================================================
import torch
device = "0" if torch.cuda.is_available() else "cpu"
print(f"Using device={device} (CUDA available: {torch.cuda.is_available()})")
if device == "cpu":
    print("⚠ No GPU detected. Training will be slow (~2-4 hrs).")
    print("  Fix: Runtime → Change runtime type → T4 GPU → Restart → re-run from Cell 1")

from ultralytics import YOLO

model = YOLO("yolov8n.pt")  # nano — fastest, smallest, good for mobile

model.train(
    data=data_yaml,
    epochs=50,
    imgsz=640,
    batch=16,
    patience=10,
    device=device,
    project="runs/train",
    name="tbs_yolov8",
    exist_ok=True,
    verbose=True,
)

# ============================================================
# CELL 5: Evaluate
# ============================================================
metrics = model.val()
print(f"mAP50: {metrics.box.map50:.3f}")
print(f"mAP50-95: {metrics.box.map:.3f}")

# ============================================================
# CELL 6: Export to TFLite (for Android)
# ============================================================
model.export(format="tflite", imgsz=640)
print("TFLite exported!")

# ============================================================
# CELL 7: Save labels.txt for inference
# ============================================================
with open("labels.txt", "w") as f:
    for name in cfg["names"]:
        f.write(name + "\n")
print("labels.txt created:", cfg["names"])

# ============================================================
# CELL 8: Download trained model to local machine
# ============================================================
from google.colab import files

# The .pt weights go to backend/model_output/yolov8_tbs.pt
files.download("runs/train/tbs_yolov8/weights/best.pt")
# The TFLite model (future use)
files.download("runs/train/tbs_yolov8/weights/best.tflite")
# Labels file
files.download("labels.txt")
print("Done! Place best.pt in backend/model_output/yolov8_tbs.pt")
