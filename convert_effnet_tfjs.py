"""
Convert EfficientNetB0 Keras model to TF.js format for on-device inference
"""

import os
import sys
import json
import shutil
import subprocess
import tempfile

os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

MODEL_DIR = "backend/model_output"
OUTPUT_DIR = "frontend/public/model_tfjs"
ANDROID_DIR = "app/src/main/assets/model_tfjs"

CLASS_NAMES = ["mentah", "kurang_matang", "matang", "terlalu_matang", "busuk"]

def find_best_model():
    candidates = [
        os.path.join(MODEL_DIR, "best_finetune.keras"),
        os.path.join(MODEL_DIR, "best_head.keras"),
        os.path.join(MODEL_DIR, "model_tbs_effnet_final.keras")
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def main():
    print("="*60)
    print("  TBS DETEKSI - EfficientNetB0 to TF.js Converter")
    print("="*60)
    
    # Find model
    model_path = find_best_model()
    if not model_path:
        print("ERROR: No model found in backend/model_output/")
        print("Expected: best_finetune.keras, best_head.keras, or model_tbs_effnet_final.keras")
        sys.exit(1)
    
    print(f"Loading model: {model_path}")
    
    # Load model
    import tensorflow as tf
    from tensorflow import keras
    model = keras.models.load_model(model_path)
    
    # Clean output dirs
    for d in [OUTPUT_DIR, ANDROID_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)
    
    # Convert using tensorflowjs
    try:
        import tensorflowjs as tfjs
    except ImportError:
        print("Installing tensorflowjs...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "tensorflowjs"])
        import tensorflowjs as tfjs
    
    print(f"Converting to TF.js format: {OUTPUT_DIR}")
    tfjs.converters.convert_keras_model(model, OUTPUT_DIR)
    
    # Write labels
    labels_path = os.path.join(OUTPUT_DIR, "labels.txt")
    with open(labels_path, "w") as f:
        for c in CLASS_NAMES:
            f.write(c + "\n")
    print(f"  ✓ Labels: {labels_path}")
    
    # Copy to Android assets
    shutil.copytree(OUTPUT_DIR, ANDROID_DIR, dirs_exist_ok=True)
    print(f"  ✓ Android assets: {ANDROID_DIR}")
    
    # Verify
    print("\nTF.js model files:")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        sz = os.path.getsize(os.path.join(OUTPUT_DIR, f))
        unit = "KB" if sz < 1024*1024 else "MB"
        val = sz/1024 if unit=="KB" else sz/1024/1024
        print(f"  {f}: {val:.1f} {unit}")
    
    print(f"\n✓ Frontend: {OUTPUT_DIR}")
    print(f"✓ Android:  {ANDROID_DIR}")
    print("\nNext steps:")
    print("  1. cd frontend && npm run build")
    print("  2. Copy dist/* to app/src/main/assets/")
    print("  3. .\\gradlew.bat assembleDebug --no-daemon")
    print("  4. adb install -r app/build/outputs/apk/debug/app-debug.apk")

if __name__ == "__main__":
    main()