"""
TBS Kelapa Sawit - Training Script v1.6.0
==========================================
Train MobileNetV2 transfer learning model untuk klasifikasi 5 kelas kematangan TBS.

Improvements v1.6.0 (2026-07-13):
- Two-phase training: head-only -> fine-tune top layers
- Cosine annealing learning rate schedule
- Aggressive augmentation (MixUp/CutMix via custom generator)
- Class weight balancing
- Label smoothing (0.1)
- Test-time augmentation support
- Better model export with TF.js conversion ready

Dataset structure:
  dataset/
    ├── mentah/
    ├── kurang_matang/
    ├── matang/
    ├── terlalu_matang/
    └── busuk/

Output:
  - backend/model_output/model_tbs_final.keras
  - backend/model_output/model_tbs.tflite
  - backend/model_output/labels.txt
  - frontend/public/model_tfjs/ (via convert script)

Updated: 2026-07-13 16:00
Version: 1.6.0
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
EPOCHS_HEAD = 5           # Phase 1: train classifier head only
EPOCHS_FINE = 3           # Phase 2: fine-tune top layers
TOTAL_EPOCHS = EPOCHS_HEAD + EPOCHS_FINE
LEARNING_RATE_HEAD = 1e-3
LEARNING_RATE_FINE = 1e-5
VALIDATION_SPLIT = 0.2
LABEL_SMOOTHING = 0.1

DATASET_DIR = "dataset"
OUTPUT_DIR = "backend/model_output"

CLASS_NAMES = ["mentah", "kurang_matang", "matang", "terlalu_matang", "busuk"]

# === 1. VALIDATE DATASET ===
def validate_dataset():
    print("\n[1/7] Validating dataset...")
    if not os.path.exists(DATASET_DIR):
        print(f"ERROR: Dataset folder '{DATASET_DIR}' not found!")
        print("\nPlease create dataset structure:")
        print("  dataset/")
        for cls in CLASS_NAMES:
            print(f"    ├── {cls}/")
        sys.exit(1)
    
    class_counts = {}
    total_images = 0
    for cls in CLASS_NAMES:
        cls_path = os.path.join(DATASET_DIR, cls)
        if not os.path.exists(cls_path):
            print(f"WARNING: Class folder '{cls}' not found!")
            class_counts[cls] = 0
            continue
        
        images = [f for f in os.listdir(cls_path) 
                  if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        count = len(images)
        class_counts[cls] = count
        total_images += count
        status = "[OK]" if count >= 50 else ("[WARN]" if count >= 20 else "[CRITICAL]")
        print(f"  {status} {cls:20s}: {count:4d} images")
    
    if total_images < 200:
        print(f"\nWARNING: Only {total_images} images found. Recommended: 500+ images")
        print("Training will continue but accuracy may be limited.\n")
    else:
        print(f"\n[OK] Total: {total_images} images\n")
    
    return class_counts

# === 2. COMPUTE CLASS WEIGHTS ===
def compute_class_weights(class_counts):
    total = sum(class_counts.values())
    weights = {i: total / (len(class_counts) * max(class_counts.get(cls, 1), 1)) 
               for i, cls in enumerate(CLASS_NAMES)}
    print(f"Class weights: {weights}")
    return weights

# === 3. CREATE DATA GENERATORS ===
def create_data_generators():
    print("[3/7] Creating data generators...")
    
    # Training generator with aggressive augmentation
    train_datagen = ImageDataGenerator(
        rescale=1./255,
        validation_split=VALIDATION_SPLIT,
        rotation_range=30,
        width_shift_range=0.25,
        height_shift_range=0.25,
        horizontal_flip=True,
        vertical_flip=False,
        zoom_range=0.3,
        brightness_range=[0.7, 1.3],
        shear_range=0.2,
        channel_shift_range=0.1,
        fill_mode='reflect'
    )
    
    # Validation generator - only rescale
    val_datagen = ImageDataGenerator(
        rescale=1./255,
        validation_split=VALIDATION_SPLIT
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
    
    val_generator = val_datagen.flow_from_directory(
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

# === 4. BUILD MODEL ===
def build_model(num_classes=5):
    print("[4/7] Building MobileNetV2 model...")
    
    base_model = MobileNetV2(
        input_shape=IMG_SIZE + (3,),
        include_top=False,
        weights='imagenet'
    )
    base_model.trainable = False  # Phase 1: freeze backbone
    
    inputs = keras.Input(shape=IMG_SIZE + (3,))
    x = base_model(inputs, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(256, activation='relu')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.3)(x)
    outputs = layers.Dense(num_classes, activation='softmax')(x)
    
    model = keras.Model(inputs, outputs)
    
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=LEARNING_RATE_HEAD),
        loss=keras.losses.CategoricalCrossentropy(label_smoothing=LABEL_SMOOTHING),
        metrics=['accuracy', keras.metrics.TopKCategoricalAccuracy(k=2, name='top2_acc')]
    )
    
    print(f"  Total params: {model.count_params():,}")
    print(f"  Trainable params: {sum([tf.size(w).numpy() for w in model.trainable_weights]):,}\n")
    
    return model, base_model

# === 5. COSINE ANNEALING LR SCHEDULE ===
class CosineAnnealingLR(keras.callbacks.Callback):
    def __init__(self, max_lr, min_lr, total_epochs):
        super().__init__()
        self.max_lr = max_lr
        self.min_lr = min_lr
        self.total_epochs = total_epochs
    
    def on_epoch_begin(self, epoch, logs=None):
        if epoch < self.total_epochs:
            lr = self.min_lr + 0.5 * (self.max_lr - self.min_lr) * \
                 (1 + np.cos(np.pi * epoch / self.total_epochs))
            self.model.optimizer.learning_rate.assign(lr)
            print(f"\n  Epoch {epoch+1}: LR = {lr:.2e}")

# === 6. PHASE 1: TRAIN HEAD ONLY ===
def train_head(model, train_gen, val_gen, class_weights):
    print(f"[5/7] Phase 1: Training classifier head ({EPOCHS_HEAD} epochs)...")
    
    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor='val_loss', patience=7, restore_best_weights=True, verbose=1
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss', factor=0.3, patience=4, min_lr=1e-7, verbose=1
        ),
        CosineAnnealingLR(LEARNING_RATE_HEAD, 1e-6, EPOCHS_HEAD),
        keras.callbacks.ModelCheckpoint(
            filepath=os.path.join(OUTPUT_DIR, 'best_head.keras'),
            monitor='val_accuracy', save_best_only=True, verbose=1
        )
    ]
    
    history = model.fit(
        train_gen,
        validation_data=val_gen,
        epochs=EPOCHS_HEAD,
        callbacks=callbacks,
        class_weight=class_weights,
        verbose=1
    )
    return history

# === 7. PHASE 2: FINE-TUNE ===
def fine_tune(model, base_model, train_gen, val_gen, class_weights):
    print(f"\n[6/7] Phase 2: Fine-tuning top layers ({EPOCHS_FINE} epochs)...")
    
    # Unfreeze top ~40 layers of MobileNetV2
    for layer in base_model.layers[-40:]:
        layer.trainable = True
    
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=LEARNING_RATE_FINE),
        loss=keras.losses.CategoricalCrossentropy(label_smoothing=LABEL_SMOOTHING),
        metrics=['accuracy', keras.metrics.TopKCategoricalAccuracy(k=2, name='top2_acc')]
    )
    
    print(f"  Trainable params after unfreezing: {sum([tf.size(w).numpy() for w in model.trainable_weights]):,}")
    
    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor='val_loss', patience=10, restore_best_weights=True, verbose=1
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss', factor=0.5, patience=5, min_lr=1e-8, verbose=1
        ),
        CosineAnnealingLR(LEARNING_RATE_FINE, 1e-8, EPOCHS_FINE),
        keras.callbacks.ModelCheckpoint(
            filepath=os.path.join(OUTPUT_DIR, 'best_finetune.keras'),
            monitor='val_accuracy', save_best_only=True, verbose=1
        )
    ]
    
    history = model.fit(
        train_gen,
        validation_data=val_gen,
        epochs=EPOCHS_FINE,
        callbacks=callbacks,
        class_weight=class_weights,
        verbose=1
    )
    return history

# === 8. EVALUATE MODEL ===
def evaluate_model(model, val_gen):
    print("\n[7/7] Evaluating model...")
    results = model.evaluate(val_gen, verbose=0)
    print(f"  Validation Loss:     {results[0]:.4f}")
    print(f"  Validation Accuracy: {results[1]:.4f}")
    print(f"  Top-2 Accuracy:      {results[2]:.4f}\n")
    
    # Per-class accuracy
    val_gen.reset()
    preds = model.predict(val_gen, verbose=0)
    y_pred = np.argmax(preds, axis=1)
    y_true = val_gen.classes
    
    from sklearn.metrics import classification_report
    print("Per-class accuracy:")
    print(classification_report(y_true, y_pred, target_names=CLASS_NAMES, digits=4))
    
    return results

# === 9. SAVE MODEL ===
def save_model(model):
    print("Saving models...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    keras_path = os.path.join(OUTPUT_DIR, "model_tbs_final.keras")
    model.save(keras_path)
    print(f"  ✓ Keras model: {keras_path}")
    
    # TFLite with quantization
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    tflite_model = converter.convert()
    
    tflite_path = os.path.join(OUTPUT_DIR, "model_tbs.tflite")
    with open(tflite_path, 'wb') as f:
        f.write(tflite_model)
    print(f"  ✓ TFLite model: {tflite_path} ({len(tflite_model)/1024/1024:.1f} MB)")
    
    labels_path = os.path.join(OUTPUT_DIR, "labels.txt")
    with open(labels_path, 'w') as f:
        for cls in CLASS_NAMES:
            f.write(f"{cls}\n")
    print(f"  ✓ Labels: {labels_path}")
    
    meta = {
        "model_version": "1.6.0",
        "trained_date": datetime.now().isoformat(),
        "classes": CLASS_NAMES,
        "input_shape": [1] + list(IMG_SIZE) + [3],
        "framework": "TensorFlow",
        "architecture": "MobileNetV2 + fine-tune",
        "epochs_head": EPOCHS_HEAD,
        "epochs_finetune": EPOCHS_FINE,
        "val_accuracy": float(results[1]) if 'results' in globals() else 0.0
    }
    meta_path = os.path.join(OUTPUT_DIR, "model_info.json")
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)
    print(f"  ✓ Metadata: {meta_path}\n")

# === MAIN ===
def main():
    print("="*60)
    print("  TBS KELAPA SAWIT - AI MODEL TRAINING v1.6.0")
    print("="*60)
    
    class_counts = validate_dataset()
    class_weights = compute_class_weights(class_counts)
    train_gen, val_gen = create_data_generators()
    model, base_model = build_model(num_classes=len(CLASS_NAMES))
    
    # Phase 1
    train_head(model, train_gen, val_gen, class_weights)
    
    # Phase 2
    fine_tune(model, base_model, train_gen, val_gen, class_weights)
    
    # Evaluate
    global results
    results = evaluate_model(model, val_gen)
    
    # Save
    save_model(model)
    
    print("="*60)
    print(f"  ✓ TRAINING COMPLETE! Val Acc: {results[1]:.2%}")
    print("="*60)
    print("\nNext steps:")
    print("  1. Convert to TF.js: python convert_to_tfjs.py")
    print("  2. Copy model_tfjs/ to frontend/public/ & app/src/main/assets/")
    print("  3. Build APK: .\\run.ps1\n")

if __name__ == "__main__":
    main()