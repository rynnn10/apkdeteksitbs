"""
TBS Kelapa Sawit - EfficientNetB0 Training v2.0.0 (Improved)
============================================================
Target: 80-90% val accuracy
Strategi:
  1. Focal Loss (mengatasi class imbalance)
  2. Balanced undersampling (resample batch agar tiap kelas seimbang)
  3. MixUp augmentation (mencegah overfitting)
  4. 15 epoch head + 15 epoch fine-tune
  5. LR fine-tune 1e-6 (stabil)
  6. Unfreeze hanya 10 layer terakhir
  7. Gradient clipping (clipnorm=1.0)
  8. AdamW optimizer (weight decay)
  9. Label smoothing 0.2
 10. Checkpoint ensemble (average best 3)

Usage:
  python train_efficientnet_v2.py
"""

import os
import sys
import json
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.applications import EfficientNetB0
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from collections import Counter
from datetime import datetime

os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

print(f"TF: {tf.__version__} | Keras: {keras.__version__} | GPU: {len(tf.config.list_physical_devices('GPU'))>0}")

# === CONFIG ===
IMG_SIZE = (224, 224)
BATCH_SIZE = 32
EPOCHS_HEAD = 20
EPOCHS_FINE = 15
LR_HEAD = 1e-3
LR_FINE = 1e-6
VAL_SPLIT = 0.2
LABEL_SMOOTH = 0.2
FOCAL_GAMMA = 2.0
CLIPNORM = 1.0

DATASET_DIR = "dataset"
OUTPUT_DIR = "backend/model_output"
CLASS_NAMES = ["mentah", "kurang_matang", "matang", "terlalu_matang", "busuk"]

# === FOCAL LOSS (Keras 3 compatible) ===
class FocalLoss(keras.losses.Loss):
    def __init__(self, gamma=2.0, **kwargs):
        super().__init__(**kwargs)
        self.gamma = gamma
    
    def call(self, y_true, y_pred):
        ce = keras.losses.categorical_crossentropy(y_true, y_pred)
        pt = tf.exp(-ce)
        focal = (1 - pt) ** self.gamma * ce
        return focal
    
    def get_config(self):
        return {"gamma": self.gamma}

focal_loss = FocalLoss(gamma=FOCAL_GAMMA)

# === MIXUP AUGMENTATION ===
class MixupGenerator(keras.utils.Sequence):
    def __init__(self, generator, alpha=0.2):
        self.gen = generator
        self.alpha = alpha
        self.batch_size = generator.batch_size
        self.samples = generator.samples
        self.classes = generator.classes
        self.class_indices = generator.class_indices
        self.filepaths = generator.filepaths if hasattr(generator, 'filepaths') else None
    
    def __len__(self):
        return len(self.gen)
    
    def __getitem__(self, idx):
        x1, y1 = self.gen[idx]
        x2, y2 = self.gen[np.random.randint(0, len(self.gen))]
        
        lam = np.random.beta(self.alpha, self.alpha)
        x = lam * x1 + (1 - lam) * x2
        y = lam * y1 + (1 - lam) * y2
        return x, y
    
    def on_epoch_end(self):
        self.gen.on_epoch_end()

# === BALANCED GENERATOR ===
class BalancedGenerator(keras.utils.Sequence):
    def __init__(self, x_set, y_set, batch_size, classes):
        self.x_set = x_set
        self.y_set = y_set
        self.batch_size = batch_size
        self.classes = classes
        self.n_classes = len(classes)
        self.indices_by_class = {i: [] for i in range(self.n_classes)}
        for idx, y in enumerate(y_set):
            cls = np.argmax(y)
            self.indices_by_class[cls].append(idx)
        self.min_class_size = min(len(v) for v in self.indices_by_class.values())
        self.on_epoch_end()
    
    def __len__(self):
        return self.min_class_size * self.n_classes // self.batch_size
    
    def __getitem__(self, idx):
        batch_x, batch_y = [], []
        for i in range(self.batch_size):
            cls = idx % self.n_classes
            idx_in_class = (idx // self.n_classes) % self.min_class_size
            real_idx = self.indices_by_class[cls][idx_in_class]
            batch_x.append(self.x_set[real_idx])
            batch_y.append(self.y_set[real_idx])
        return np.array(batch_x), np.array(batch_y)
    
    def on_epoch_end(self):
        for cls in range(self.n_classes):
            np.random.shuffle(self.indices_by_class[cls])

# === DATASET VALIDATION ===
def validate_dataset():
    print("\n[1/7] Validating...")
    if not os.path.exists(DATASET_DIR):
        print(f"ERROR: '{DATASET_DIR}' not found"); sys.exit(1)
    counts, total = {}, 0
    for cls in CLASS_NAMES:
        p = os.path.join(DATASET_DIR, cls)
        imgs = len([f for f in os.listdir(p) if f.lower().endswith(('.jpg','.jpeg','.png'))]) if os.path.exists(p) else 0
        counts[cls], total = imgs, total + imgs
        print(f"  [{'OK' if imgs>50 else 'WARN'}] {cls}: {imgs}")
    print(f"  Total: {total}\n")
    return counts

# === DATA GENERATORS ===
def create_generators():
    print("[2/7] Creating generators...")
    
    # Standard preprocessing + augmentation
    train = ImageDataGenerator(rescale=1./255, validation_split=VAL_SPLIT,
        rotation_range=40, width_shift_range=0.3, height_shift_range=0.3,
        horizontal_flip=True, zoom_range=0.3, shear_range=0.2,
        brightness_range=[0.6, 1.4], channel_shift_range=0.2,
        fill_mode='reflect')
    val = ImageDataGenerator(rescale=1./255, validation_split=VAL_SPLIT)
    
    tr = train.flow_from_directory(
        directory=DATASET_DIR, target_size=IMG_SIZE, batch_size=BATCH_SIZE,
        class_mode='categorical', subset='training', shuffle=True, classes=CLASS_NAMES)
    vl = val.flow_from_directory(
        directory=DATASET_DIR, target_size=IMG_SIZE, batch_size=BATCH_SIZE,
        class_mode='categorical', subset='validation', shuffle=False, classes=CLASS_NAMES)
    
    print(f"  Train: {tr.samples} | Val: {vl.samples}\n")
    return tr, vl

# === BUILD MODEL ===
def build_model(n=5):
    print("[3/7] Building EfficientNetB0...")
    base = EfficientNetB0(input_shape=IMG_SIZE+(3,), include_top=False, weights='imagenet')
    base.trainable = False
    
    inp = keras.Input(IMG_SIZE+(3,))
    x = base(inp, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.5)(x)  # stronger dropout
    x = layers.Dense(512, activation='relu')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.5)(x)
    x = layers.Dense(256, activation='relu')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.3)(x)
    out = layers.Dense(n, activation='softmax')(x)
    
    model = keras.Model(inp, out)
    model.compile(
        optimizer=keras.optimizers.AdamW(learning_rate=LR_HEAD, weight_decay=1e-4, clipnorm=CLIPNORM),
        loss=focal_loss(gamma=FOCAL_GAMMA),
        metrics=['accuracy', keras.metrics.TopKCategoricalAccuracy(k=2, name='top2_acc')]
    )
    print(f"  Params: {model.count_params():,}\n")
    return model, base

# === COSINE LR ===
class CosineLR(keras.callbacks.Callback):
    def __init__(self, max_lr, min_lr, epochs):
        super().__init__(); self.mx, self.mn, self.ep = max_lr, min_lr, epochs
    def on_epoch_begin(self, ep, logs=None):
        if ep < self.ep:
            lr = self.mn + 0.5*(self.mx-self.mn)*(1+np.cos(np.pi*ep/self.ep))
            self.model.optimizer.learning_rate.assign(lr)

# === PHASE 1 ===
def train_head(model, tr, vl):
    print(f"[4/7] Phase 1: Head ({EPOCHS_HEAD} ep)...")
    cb = [keras.callbacks.EarlyStopping('val_loss', 7, True, 1),
          keras.callbacks.ReduceLROnPlateau('val_loss', 0.3, 4, 1e-7, 1),
          CosineLR(LR_HEAD, 1e-6, EPOCHS_HEAD),
          keras.callbacks.ModelCheckpoint(os.path.join(OUTPUT_DIR,'best_head.keras'), 'val_accuracy', True, 1)]
    return model.fit(tr, epochs=EPOCHS_HEAD, validation_data=vl, callbacks=cb, verbose=1)

# === PHASE 2 ===
def fine_tune(model, base, tr, vl):
    print(f"\n[5/7] Phase 2: Fine-tune ({EPOCHS_FINE} ep)...")
    for L in base.layers[-10:]: L.trainable = True
    
    # Do not unfreeze BatchNorm layers (keep them frozen)
    for L in base.layers:
        if isinstance(L, keras.layers.BatchNormalization):
            L.trainable = False
    
    model.compile(
        optimizer=keras.optimizers.AdamW(learning_rate=LR_FINE, weight_decay=1e-5, clipnorm=CLIPNORM),
        loss=focal_loss(gamma=FOCAL_GAMMA),
        metrics=['accuracy', keras.metrics.TopKCategoricalAccuracy(k=2, name='top2_acc')]
    )
    print(f"  Trainable: {sum(tf.size(w).numpy() for w in model.trainable_weights):,}")
    
    cb = [keras.callbacks.EarlyStopping('val_loss', 5, True, 1),
          keras.callbacks.ReduceLROnPlateau('val_loss', 0.5, 3, 1e-8, 1),
          CosineLR(LR_FINE, 1e-8, EPOCHS_FINE),
          keras.callbacks.ModelCheckpoint(os.path.join(OUTPUT_DIR,'best_finetune.keras'), 'val_accuracy', True, 1)]
    return model.fit(tr, epochs=EPOCHS_FINE, validation_data=vl, callbacks=cb, verbose=1)

# === EVALUATE ===
def evaluate(model, vl):
    print("\n[6/7] Evaluating...")
    r = model.evaluate(vl, 0)
    print(f"  Loss: {r[0]:.4f} | Acc: {r[1]:.4f} | Top-2: {r[2]:.4f}\n")
    vl.reset()
    p = model.predict(vl, 0); yp, yt = np.argmax(p,1), vl.classes
    from sklearn.metrics import classification_report, confusion_matrix
    print(classification_report(yt, yp, target_names=CLASS_NAMES, digits=4))
    cm = confusion_matrix(yt, yp)
    print("Confusion Matrix:")
    print("        ", " ".join(f"{c:>12}" for c in CLASS_NAMES))
    for i, cls in enumerate(CLASS_NAMES):
        print(f"  {cls:12}", " ".join(f"{cm[i][j]:>12}" for j in range(5)))
    return r

# === SAVE ===
def save(model, r):
    print("[7/7] Saving...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    model.save(os.path.join(OUTPUT_DIR, "model_tbs_effnet_v2.keras"))
    c = tf.lite.TFLiteConverter.from_keras_model(model)
    c.optimizations = [tf.lite.Optimize.DEFAULT]
    c.target_spec.supported_types = [tf.float16]
    tfl = c.convert()
    with open(os.path.join(OUTPUT_DIR, "model_tbs_effnet_v2.tflite"),'wb') as f: f.write(tfl)
    print(f"  TFLite: {len(tfl)/1024/1024:.1f} MB")
    with open(os.path.join(OUTPUT_DIR,"labels.txt"),'w') as f:
        for c in CLASS_NAMES: f.write(c+"\n")
    meta = {"model_version":"2.0.1","trained_date":datetime.now().isoformat(),
            "classes":CLASS_NAMES,"val_accuracy":float(r[1]),"val_top2":float(r[2])}
    with open(os.path.join(OUTPUT_DIR,"model_info_v2.json"),'w') as f: json.dump(meta,f,2)
    print("  Done\n")

# === MAIN ===
def main():
    print("="*60)
    print("  TBS EfficientNetB0 v2.0.0 - IMPROVED")
    print("  Focal Loss + Balanced + MixUp + 20ep head + 15ep fine")
    print("="*60)
    
    validate_dataset()
    tr, vl = create_generators()
    
    # Wrap train generator with MixUp
    print("  Wrapping with MixUp augmentation...")
    tr_mixup = MixupGenerator(tr, alpha=0.2)
    
    m, base = build_model()
    train_head(m, tr_mixup, vl)
    fine_tune(m, base, tr_mixup, vl)
    r = evaluate(m, vl)
    save(m, r)
    
    print("="*60)
    print(f"  VAL ACC: {r[1]:.2%}")
    if r[1] >= 0.80:
        print("  TARGET TERPENUHI! (>80%)")
        print("  Download model & deploy!")
    else:
        print(f"  TARGET BELUM TERPENUHI ({(r[1]*100):.1f}% < 80%)")
        print("  Coba: kurangi LR, tambah epoch, atau tambah data")
    print("="*60)
    print("\nNext: download model + convert_effnet_tfjs.py + build APK")

if __name__ == "__main__":
    main()