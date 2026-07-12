"""
Konversi model Keras (.h5/.keras) hasil training ke TensorFlow.js format.
Output: frontend/public/model_tfjs/

Usage:
    python convert_to_tfjs.py [path/to/model.keras] [path/to/labels.txt]

Install:
    pip install tensorflowjs
"""
import sys
import os
import json

def main():
    model_path = sys.argv[1] if len(sys.argv) > 1 else "model_output/model_tbs_final.keras"
    labels_path = sys.argv[2] if len(sys.argv) > 2 else "model_output/labels.txt"
    out_dir = "model_tfjs"

    os.makedirs(out_dir, exist_ok=True)

    # Convert Keras -> TFJS GraphModel
    print(f"Converting {model_path} -> {out_dir}")
    os.system(f"tensorflowjs_converter --input_format=keras {model_path} {out_dir}")

    # Read labels
    if os.path.exists(labels_path):
        with open(labels_path) as f:
            labels = [line.strip() for line in f if line.strip()]
    else:
        labels = ["mentah", "kurang_matang", "matang", "terlalu_matang", "busuk"]

    # Write labels.json
    with open(os.path.join(out_dir, "labels.json"), "w") as f:
        json.dump(labels, f, indent=2)

    print(f"Labels: {labels}")
    print(f"Output: {out_dir}/")
    print()
    print("Next: copy model_tfjs/ to frontend/public/model_tfjs/")
    print("Then rebuild frontend or build Android APK.")

if __name__ == "__main__":
    main()
