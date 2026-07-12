"""
Buat dummy TFLite model untuk testing aplikasi tanpa perlu training.
Jalankan: python generate_dummy_model.py
"""
import os
import numpy as np

def create_dummy_tflite(output_dir="model_output"):
    os.makedirs(output_dir, exist_ok=True)
    tflite_path = os.path.join(output_dir, "model_tbs.tflite")

    try:
        import tensorflow as tf
        # Buat model minimal MobileNetV2 untuk testing
        base = tf.keras.applications.MobileNetV2(
            input_shape=(224, 224, 3), include_top=False, weights=None  # tanpa pretrained
        )
        x = tf.keras.layers.GlobalAveragePooling2D()(base.output)
        x = tf.keras.layers.Dense(64, activation='relu')(x)
        out = tf.keras.layers.Dense(5, activation='softmax')(x)
        model = tf.keras.Model(inputs=base.input, outputs=out)

        converter = tf.lite.TFLiteConverter.from_keras_model(model)
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        tflite_model = converter.convert()

        with open(tflite_path, "wb") as f:
            f.write(tflite_model)
        print(f"Dummy TFLite model created: {tflite_path}")
        print(f"Size: {len(tflite_model) / 1024:.1f} KB")
        print("NOTE: Ini model DUMMY (random weights). Training diperlukan untuk hasil akurat.")
        return True
    except ImportError as e:
        print(f"TensorFlow not available: {e}")
        print("Skipping dummy model creation. Place a real model_tbs.tflite manually.")
        return False

if __name__ == "__main__":
    create_dummy_tflite()
