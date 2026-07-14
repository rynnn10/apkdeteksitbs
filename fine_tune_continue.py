"""
Fine-tuning continuation script - load best_head.keras and fine-tune top layers
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

os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

print(f"TensorFlow version: {tf.__version__}")
print(f"Keras version: {keras.__version__}")

IMG_SIZE = (224, 224)
BATCH_SIZE = 32
EPOCHS_FINE = 3
LEARNING_RATE_FINE = 1e-5
VALIDATION_SPLIT = 0.2
LABEL_SMOOTHING = 0.1

DATASET_DIR = "dataset"
OUTPUT_DIR = "backend/model_output"
CLASS_NAMES = ["mentah", "kurang_matang", "matang", "terlalu_matang", "busuk"]

def compute_class_weights():
    class_counts = {}
    total = 0
    for cls in CLASS_NAMES:
        cls_path = os.path.join(DATASET_DIR, cls)
        if os.path.exists(cls_path):
            images = [f for f in os.listdir(cls_path) 
                      if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            class_counts[cls] = len(images)
            total += len(images)
        else:
            class_counts[cls] = 0
    
    weights = {i: total / (len(CLASS_NAMES) * max(class_counts.get(cls, 1), 1)) 
               for i, cls in enumerate(CLASS_NAMES)}
    print(f"Class weights: {weights}")
    return weights

def create_generators():
    print("Creating data generators...")
    
    train_datagen = ImageDataGenerator(
        rescale=1./255,
        validation_split=VALIDATION_SPLIT,
        rotation_range=30,
        width_shift_range=0.25,
        height_shift_range=0.25,
        horizontal_flip=True,
        zoom_range=0.3,
        brightness_range=[0.7, 1.3],
        shear_range=0.2,
        channel_shift_range=0.1,
        fill_mode='reflect'
    )
    
    val_datagen = ImageDataGenerator(
        rescale=1./255,
        validation_split=VALIDATION_SPLIT
    )
    
    train_gen = train_datagen.flow_from_directory(
        DATASET_DIR, target_size=IMG_SIZE, batch_size=BATCH_SIZE,
        class_mode='categorical', subset='training', shuffle=True, classes=CLASS_NAMES
    )
    
    val_gen = val_datagen.flow_from_directory(
        DATASET_DIR, target_size=IMG_SIZE, batch_size=BATCH_SIZE,
        class_mode='categorical', subset='validation', shuffle=False, classes=CLASS_NAMES
    )
    
    print(f"  Train: {train_gen.samples}, Val: {val_gen.samples}")
    return train_gen, val_gen

def load_and_unfreeze():
    print("Loading best_head.keras...")
    model = keras.models.load_model(os.path.join(OUTPUT_DIR, "best_head.keras"))
    
    # Find base model (MobileNetV2 layer)
    base_model = None
    for layer in model.layers:
        if isinstance(layer, keras.Model) and 'mobilenetv2' in layer.name.lower():
            base_model = layer
            break
    
    if base_model is None:
        # Find by checking layer types
        for layer in model.layers:
            if hasattr(layer, 'layers') and len(layer.layers) > 100:
                base_model = layer
                break
    
    if base_model is None:
        raise ValueError("Could not find MobileNetV2 base model")
    
    print(f"Found base model: {base_model.name}")
    
    # Unfreeze top ~40 layers
    for layer in base_model.layers[-40:]:
        layer.trainable = True
    
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=LEARNING_RATE_FINE),
        loss=keras.losses.CategoricalCrossentropy(label_smoothing=LABEL_SMOOTHING),
        metrics=['accuracy', keras.metrics.TopKCategoricalAccuracy(k=2, name='top2_acc')]
    )
    
    print(f"  Trainable params: {sum([tf.size(w).numpy() for w in model.trainable_weights]):,}")
    return model, base_model

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

def main():
    print("="*60)
    print("  TBS KELAPA SAWIT - FINE-TUNING PHASE")
    print("="*60)
    
    class_weights = compute_class_weights()
    train_gen, val_gen = create_generators()
    model, base_model = load_and_unfreeze()
    
    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor='val_loss', patience=5, restore_best_weights=True, verbose=1
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss', factor=0.5, patience=3, min_lr=1e-8, verbose=1
        ),
        CosineAnnealingLR(LEARNING_RATE_FINE, 1e-8, EPOCHS_FINE),
        keras.callbacks.ModelCheckpoint(
            filepath=os.path.join(OUTPUT_DIR, 'best_finetune.keras'),
            monitor='val_accuracy', save_best_only=True, verbose=1
        )
    ]
    
    print(f"\nStarting fine-tuning ({EPOCHS_FINE} epochs)...")
    history = model.fit(
        train_gen, validation_data=val_gen,
        epochs=EPOCHS_FINE, callbacks=callbacks,
        class_weight=class_weights, verbose=1
    )
    
    print("\nEvaluating...")
    results = model.evaluate(val_gen, verbose=0)
    print(f"  Val Loss: {results[0]:.4f}")
    print(f"  Val Acc:  {results[1]:.4f}")
    print(f"  Top-2:    {results[2]:.4f}")
    
    # Per-class accuracy
    val_gen.reset()
    preds = model.predict(val_gen, verbose=0)
    y_pred = np.argmax(preds, axis=1)
    y_true = val_gen.classes
    
    from sklearn.metrics import classification_report
    print("\nPer-class:")
    print(classification_report(y_true, y_pred, target_names=CLASS_NAMES, digits=4))
    
    # Save final model
    print("\nSaving final model...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    model.save(os.path.join(OUTPUT_DIR, "model_tbs_final.keras"))
    
    # TFLite
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    tflite_model = converter.convert()
    with open(os.path.join(OUTPUT_DIR, "model_tbs.tflite"), 'wb') as f:
        f.write(tflite_model)
    print(f"  ✓ TFLite: {len(tflite_model)/1024/1024:.1f} MB")
    
    # Labels
    with open(os.path.join(OUTPUT_DIR, "labels.txt"), 'w') as f:
        for cls in CLASS_NAMES:
            f.write(f"{cls}\n")
    
    # Metadata
    meta = {
        "model_version": "1.6.0",
        "trained_date": datetime.now().isoformat(),
        "classes": CLASS_NAMES,
        "input_shape": [1, 224, 224, 3],
        "framework": "TensorFlow",
        "architecture": "MobileNetV2 + fine-tune",
        "val_accuracy": float(results[1])
    }
    with open(os.path.join(OUTPUT_DIR, "model_info.json"), 'w') as f:
        json.dump(meta, f, indent=2)
    
    print("\n" + "="*60)
    print(f"  ✓ FINE-TUNING COMPLETE! Val Acc: {results[1]:.2%}")
    print("="*60)
    print("\nNext: python convert_to_tfjs.py")

if __name__ == "__main__":
    main()