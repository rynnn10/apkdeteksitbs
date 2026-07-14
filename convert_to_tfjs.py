"""
Convert Keras model to TF.js format for on-device inference
"""
import os
import json
import subprocess
import shutil
import sys

MODEL_DIR = "backend/model_output"
OUTPUT_DIR = "frontend/public/model_tfjs"

CLASS_NAMES = ["mentah", "kurang_matang", "matang", "terlalu_matang", "busuk"]

def convert_keras_to_tfjs():
    keras_path = os.path.join(MODEL_DIR, "model_tbs_final.keras")
    best_path = os.path.join(MODEL_DIR, "best_finetune.keras")
    head_path = os.path.join(MODEL_DIR, "best_head.keras")
    
    # Use best_finetune first, fallback to best_head, then final
    model_path = None
    for p in [best_path, head_path, keras_path]:
        if os.path.exists(p):
            model_path = p
            break
    
    if not model_path:
        print("No model found!")
        sys.exit(1)
    
    print(f"Loading model: {model_path}")
    
    import tensorflow as tf
    from tensorflow import keras
    model = keras.models.load_model(model_path)
    
    # Save as SavedModel for TFJS converter
    import tempfile
    saved_model_dir = tempfile.mkdtemp()
    model.export(saved_model_dir)
    print(f"SavedModel: {saved_model_dir}")
    
    # Use tensorflowjs_converter
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    cmd = [
        sys.executable, "-m", "tensorflowjs.converters.converter",
        "--input_format=tf_saved_model",
        "--output_format=tfjs_graph_model",
        "--signature_name=serving_default",
        f"--saved_model_tags=serve",
        saved_model_dir,
        OUTPUT_DIR
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print("STDOUT:", result.stdout[-500:])
        if result.returncode != 0:
            print("STDERR:", result.stderr[-500:])
            raise RuntimeError(f"Converter return code: {result.returncode}")
    except FileNotFoundError:
        print("tensorflowjs converter not found, trying alternative...")
        # Try using tfjs directly
        try:
            import tensorflowjs as tfjs
            tfjs.converters.convert_tf_saved_model(
                saved_model_dir, OUTPUT_DIR
            )
        except ImportError:
            print("Installing tensorflowjs...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "tensorflowjs"
            ])
            import tensorflowjs as tfjs
            tfjs.converters.convert_keras_model(model, OUTPUT_DIR)
    
    # Write labels
    with open(os.path.join(OUTPUT_DIR, "labels.txt"), "w") as f:
        for cls in CLASS_NAMES:
            f.write(f"{cls}\n")
    
    # Verify
    files = os.listdir(OUTPUT_DIR)
    print("\nTF.js model files:")
    for f in sorted(files):
        path = os.path.join(OUTPUT_DIR, f)
        size = os.path.getsize(path)
        print(f"  {f}: {size/1024:.1f} KB" if size < 1024*1024 else f"  {f}: {size/1024/1024:.1f} MB")
    
    # Copy to Android assets
    android_assets = "app/src/main/assets/model_tfjs"
    if os.path.exists(android_assets):
        shutil.rmtree(android_assets)
    shutil.copytree(OUTPUT_DIR, android_assets)
    print(f"\nCopied to Android assets: {android_assets}")
    
    print("\nDone! TF.js model ready.")
    print(f"  Frontend: {OUTPUT_DIR}")
    print(f"  Android:  {android_assets}")

if __name__ == "__main__":
    convert_keras_to_tfjs()