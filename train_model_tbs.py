"""
TBS Kelapa Sawit - Training Script
===================================
Train MobileNetV2 transfer learning model untuk klasifikasi 5 kelas kematangan TBS.

Dataset structure:
  dataset/
    ├── mentah/
    ├── kurang_matang/
    ├── matang/
    ├── terlalu_matang/
    └── busuk/

Output:
  - model_output/model_tbs_final.keras
  - model_output/model_tbs.tflite
  - model_output/labels.txt

Updated: 2026-07-12 10:59 UTC
Version: 1.0.0
"""
import os
import sys
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from pathlib import Path
import json
from datetime import datetime

print(f"TensorFlow version: {tf.__version__}")
print(f"Keras version: {keras.__version__}")

# === CONFIGURATION ===
IMG_SIZE = (224, 224)
BATCH_SIZE = 32
EPOCHS = 20
LEARNING_RATE = 0.001
VALIDATION_SPLIT = 0.2

DATASET_DIR = "dataset"
OUTPUT_DIR = "backend/model_output"

CLASS_NAMES = ["mentah", "kurang_matang", "matang", "terlalu_matang", "busuk"]

# === 1. VALIDATE DATASET ===
def validate_dataset():
    print("\n[1/6] Validating dataset...")
    if not os.path.exists(DATASET_DIR):
        print(f"ERROR: Dataset folder '{DATASET_DIR}' not found!")
        print("\nPlease create dataset structure:")
        print("  dataset/")
        for cls in CLASS_NAMES:
            print(f"    ├── {cls}/")
        sys.exit(1)
    
    total_images = 0
    for cls in CLASS_NAMES:
        cls_path = os.path.join(DATASET_DIR, cls)
        if not os.path.exists(cls_path):
            print(f"WARNING: Class folder '{cls}' not found!")
            continue
        
        images = [f for f in os.listdir(cls_path) 
                  if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        count = len(images)
        total_images += count
        status = "✓" if count >= 20 else "⚠"
        print(f"  {status} {cls:20s}: {count:4d} images")
    
    if total_images < 100:
        print(f"\nWARNING: Only {total_images} images found. Recommended: 200+ images")
        print("Training will continue but accuracy may be low.\n")
    else:
        print(f"\n✓ Total: {total_images} images\n")

# === 2. CREATE DATA GENERATORS ===
def create_data_generators():
    print("[2/6] Creating data generators...")
    
    train_datagen = ImageDataGenerator(
        rescale=1./255,
        validation_split=VALIDATION_SPLIT,
        rotation_range=20,
        width_shift_range=0.2,
        height_shift_range=0.2,
        horizontal_flip=True,
        zoom_range=0.2,
        brightness_range=[0.8, 1.2],
        fill_mode='nearest'
    )
    
    train_generator = train_datagen.flow_from_directory(
        DATASET_DIR,
        target_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        subset='training',
        shuffle=True,
        classes=CLASS_NAMES
    )
    
    val_generator = train_datagen.flow_from_directory(
        DATASET_DIR,
        target_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        subset='validation',
        shuffle=False,
        classes=CLASS_NAMES
    )
    
    print(f"  Train samples: {train_generator.samples}")
    print(f"  Val samples:   {val_generator.samples}")
    print(f"  Classes: {train_generator.class_indices}\n")
    
    return train_generator, val_generator

# === 3. BUILD MODEL ===
def build_model(num_classes=5):
    print("[3/6] Building MobileNetV2 model...")
    
    base_model = MobileNetV2(
        input_shape=IMG_SIZE + (3,),
        include_top=False,
        weights='imagenet'
    )
    base_model.trainable = False
    
    inputs = keras.Input(shape=IMG_SIZE + (3,))
    x = base_model(inputs, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.2)(x)
    x = layers.Dense(128, activation='relu')(x)
    x = layers.Dropout(0.2)(x)
    outputs = layers.Dense(num_classes, activation='softmax')(x)
    
    model = keras.Model(inputs, outputs)
    
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss='categorical_crossentropy',
        metrics=['accuracy', keras.metrics.TopKCategoricalAccuracy(k=2, name='top2_acc')]
    )
    
    print(f"  Total params: {model.count_params():,}")
    print(f"  Trainable params: {sum([tf.size(w).numpy() for w in model.trainable_weights]):,}\n")
    
    return model

# === 4. TRAIN MODEL ===
def train_model(model, train_gen, val_gen):
    print("[4/6] Training model...")
    
    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=5,
            restore_best_weights=True,
            verbose=1
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=3,
            min_lr=1e-7,
            verbose=1
        )
    ]
    
    history = model.fit(
        train_gen,
        validation_data=val_gen,
        epochs=EPOCHS,
        callbacks=callbacks,
        verbose=1
    )
    
    return history

# === 5. EVALUATE MODEL ===
def evaluate_model(model, val_gen):
    print("\n[5/6] Evaluating model...")
    
    results = model.evaluate(val_gen, verbose=0)
    print(f"  Validation Loss:     {results[0]:.4f}")
    print(f"  Validation Accuracy: {results[1]:.4f}")
    print(f"  Top-2 Accuracy:      {results[2]:.4f}\n")
    
    return results

# === 6. SAVE MODEL ===
def save_model(model):
    print("[6/6] Saving model...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    keras_path = os.path.join(OUTPUT_DIR, "model_tbs_final.keras")
    model.save(keras_path)
    print(f"  ✓ Keras model: {keras_path}")
    
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    tflite_model = converter.convert()
    
    tflite_path = os.path.join(OUTPUT_DIR, "model_tbs.tflite")
    with open(tflite_path, 'wb') as f:
        f.write(tflite_model)
    print(f"  ✓ TFLite model: {tflite_path}")
    
    labels_path = os.path.join(OUTPUT_DIR, "labels.txt")
    with open(labels_path, 'w') as f:
        for cls in CLASS_NAMES:
            f.write(f"{cls}\n")
    print(f"  ✓ Labels: {labels_path}")
    
    meta = {
        "model_version": "1.0.0",
        "trained_date": datetime.now().isoformat(),
        "classes": CLASS_NAMES,
        "input_shape": [1] + list(IMG_SIZE) + [3],
        "framework": "TensorFlow",
        "architecture": "MobileNetV2"
    }
    meta_path = os.path.join(OUTPUT_DIR, "model_info.json")
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)
    print(f"  ✓ Metadata: {meta_path}\n")

# === MAIN ===
def main():
    print("="*60)
    print("  TBS KELAPA SAWIT - AI MODEL TRAINING")
    print("="*60)
    
    validate_dataset()
    train_gen, val_gen = create_data_generators()
    model = build_model(num_classes=len(CLASS_NAMES))
    history = train_model(model, train_gen, val_gen)
    evaluate_model(model, val_gen)
    save_model(model)
    
    print("="*60)
    print("  ✓ TRAINING COMPLETE!")
    print("="*60)
    print("\nNext steps:")
    print("  1. Test model: python backend/main.py")
    print("  2. Build APK: .\\run.ps1")
    print("  3. For web: Copy model_tfjs/ to frontend/public/\n")

if __name__ == "__main__":
    main()
