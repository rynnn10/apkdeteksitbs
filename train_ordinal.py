#!/usr/bin/env python3
"""
TBS Ordinal Regression - Target 90%+
Classes as ordered: mentah=0, kurang_matang=1, matang=2, terlalu_matang=3, busuk=4
Uses CORAL loss + MSE for ordered prediction
"""
import os, json, numpy as np, tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import classification_report, confusion_matrix, mean_absolute_error

os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

DATASET_DIR = "dataset"
OUTPUT_DIR = "backend/model_output"
IMG_SIZE = (224, 224)
BATCH_SIZE = 32
VAL_SPLIT = 0.2
SEED = 42
EPOCHS_HEAD = 40
EPOCHS_FINE = 30
LR_HEAD = 1e-3
LR_FINE = 5e-6
CLIPNORM = 1.0
WEIGHT_DECAY = 1e-4
UNFREEZE_LAYERS = 25
MIXUP_ALPHA = 0.3

CLASS_NAMES = ["mentah", "kurang_matang", "matang", "terlalu_matang", "busuk"]
NUM_CLASSES = len(CLASS_NAMES)
ORDINAL_VALUES = np.array([0, 1, 2, 3, 4], dtype=np.float32)

os.makedirs(OUTPUT_DIR, exist_ok=True)

# === CORAL LOSS (Ordinal) ===
class CoralOrdinalLoss(keras.losses.Loss):
    """CORAL: Consistent Rank Logits - ordinal regression loss"""
    def __init__(self, num_classes=5, **kwargs):
        super().__init__(**kwargs)
        self.num_classes = num_classes
    
    def call(self, y_true, y_pred):
        # y_true: (batch, num_classes-1) binary targets for each threshold
        # y_pred: (batch, num_classes-1) logits
        return tf.reduce_mean(
            tf.nn.sigmoid_cross_entropy_with_logits(labels=y_true, logits=y_pred)
        )
    
    def get_config(self):
        return {"num_classes": self.num_classes}

# === CONVERT CLASS INDEX TO ORDINAL TARGETS ===
def to_ordinal_targets(y_idx, num_classes=5):
    """Convert class index (0-4) to CORAL binary targets (4 thresholds)"""
    # For class k: thresholds 0..k-1 are 1, k..end are 0
    # e.g., class 2 -> [1, 1, 0, 0]
    batch = tf.shape(y_idx)[0]
    thresholds = tf.range(num_classes - 1, dtype=tf.int32)  # [0,1,2,3]
    y_idx_exp = tf.expand_dims(tf.cast(y_idx, tf.int32), -1)  # (batch,1)
    thresholds_exp = tf.expand_dims(thresholds, 0)  # (1,4)
    targets = tf.cast(thresholds_exp < y_idx_exp, tf.float32)  # (batch,4)
    return targets

# === MIXUP GENERATOR ===
class MixupGenerator(keras.utils.Sequence):
    def __init__(self, generator, alpha=0.2):
        self.gen = generator
        self.alpha = alpha
        self.batch_size = generator.batch_size
        self.samples = generator.samples
        self.classes = generator.classes
        self.class_indices = generator.class_indices
        self.filepaths = getattr(generator, 'filepaths', None)
    
    def __len__(self):
        return len(self.gen)
    
    def __getitem__(self, idx):
        x1, y1 = self.gen[idx]
        x2, y2 = self.gen[np.random.randint(0, len(self.gen))]
        
        b = min(x1.shape[0], x2.shape[0])
        if x1.shape[0] != b: x1, y1 = x1[:b], y1[:b]
        if x2.shape[0] != b: x2, y2 = x2[:b], y2[:b]
        
        lam = np.random.beta(self.alpha, self.alpha, b).reshape(-1, 1, 1, 1)
        lam_y = np.random.beta(self.alpha, self.alpha, b).reshape(-1, 1)
        
        x = lam * x1 + (1 - lam) * x2
        
        # For ordinal: mix class indices, then convert to ordinal targets
        y1_idx = np.argmax(y1, axis=1) if y1.ndim > 1 else y1
        y2_idx = np.argmax(y2, axis=1) if y2.ndim > 1 else y2
        y_mixed_idx = lam_y.flatten() * y1_idx + (1 - lam_y.flatten()) * y2_idx
        y_mixed_idx = np.round(y_mixed_idx).astype(np.int32)
        y_mixed_idx = np.clip(y_mixed_idx, 0, NUM_CLASSES - 1)
        
        y_ordinal = to_ordinal_targets(y_mixed_idx, NUM_CLASSES).numpy()
        return x, y_ordinal
    
    def on_epoch_end(self):
        self.gen.on_epoch_end()

# === COSINE ANNEALING LR ===
class CosineLR(keras.callbacks.Callback):
    def __init__(self, max_lr, min_lr, epochs):
        super().__init__()
        self.mx, self.mn, self.ep = max_lr, min_lr, epochs
    
    def on_epoch_begin(self, epoch, logs=None):
        if epoch < self.ep:
            lr = self.mn + 0.5 * (self.mx - self.mn) * (1 + np.cos(np.pi * epoch / self.ep))
            self.model.optimizer.learning_rate.assign(lr)

# === DATA GENERATORS ===
def create_generators():
    print("[1/7] Creating generators...")
    
    train_datagen = ImageDataGenerator(
        rescale=1./255, validation_split=VAL_SPLIT,
        rotation_range=45, width_shift_range=0.3, height_shift_range=0.3,
        horizontal_flip=True, vertical_flip=True, zoom_range=0.4,
        shear_range=0.3, brightness_range=[0.5, 1.5],
        channel_shift_range=0.3, fill_mode='reflect'
    )
    val_datagen = ImageDataGenerator(rescale=1./255, validation_split=VAL_SPLIT)
    
    train_gen = train_datagen.flow_from_directory(
        DATASET_DIR, target_size=IMG_SIZE, batch_size=BATCH_SIZE,
        class_mode='categorical', subset='training', shuffle=True,
        classes=CLASS_NAMES, seed=SEED)
    val_gen = val_datagen.flow_from_directory(
        DATASET_DIR, target_size=IMG_SIZE, batch_size=BATCH_SIZE,
        class_mode='categorical', subset='validation', shuffle=False,
        classes=CLASS_NAMES, seed=SEED)
    
    print(f"  Train: {train_gen.samples} | Val: {val_gen.samples}")
    return train_gen, val_gen

def get_class_weights(generator):
    print("[2/7] Computing class weights...")
    cls_weights = compute_class_weight('balanced', classes=np.unique(generator.classes), y=generator.classes)
    cw_dict = {i: w for i, w in enumerate(cls_weights)}
    print(f"  Weights: {dict(zip(CLASS_NAMES, cls_weights))}")
    return cw_dict

# === BUILD ORDINAL MODEL ===
def build_model():
    print("[3/7] Building MobileNetV2 Ordinal...")
    base = MobileNetV2(input_shape=IMG_SIZE+(3,), include_top=False, weights='imagenet')
    base.trainable = False
    
    inp = keras.Input(IMG_SIZE+(3,))
    x = base(inp, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.5)(x)
    x = layers.Dense(512, activation='relu', kernel_regularizer=keras.regularizers.l2(1e-4))(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.5)(x)
    x = layers.Dense(256, activation='relu', kernel_regularizer=keras.regularizers.l2(1e-4))(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.3)(x)
    # Output: num_classes-1 logits for CORAL thresholds
    out = layers.Dense(NUM_CLASSES - 1, activation=None)(x)
    
    model = keras.Model(inp, out)
    model.compile(
        optimizer=keras.optimizers.AdamW(learning_rate=LR_HEAD, weight_decay=WEIGHT_DECAY, clipnorm=CLIPNORM),
        loss=CoralOrdinalLoss(num_classes=NUM_CLASSES),
        metrics=['accuracy']  # binary accuracy per threshold
    )
    print(f"  Params: {model.count_params():,}")
    return model, base

# === ORDINAL VALIDATION WRAPPER ===
class OrdinalValGenerator(keras.utils.Sequence):
    def __init__(self, base_gen, num_classes):
        self.gen = base_gen
        self.num_classes = num_classes
    
    def __len__(self):
        return len(self.gen)
    
    def __getitem__(self, idx):
        x, y = self.gen[idx]
        if y.ndim == 2 and y.shape[1] == self.num_classes:
            y = np.argmax(y, axis=1)
        return x, to_ordinal_targets(y, self.num_classes)
    
    def on_epoch_end(self):
        self.gen.on_epoch_end()
    
    def reset(self):
        self.gen.reset()


# === PHASE 1: HEAD TRAINING ===
def train_head(model, train_gen, val_gen, class_weights):
    print(f"\n[4/7] Phase 1: Head ({EPOCHS_HEAD} ep)...")
    train_mix = MixupGenerator(train_gen, alpha=MIXUP_ALPHA)
    val_ordinal = OrdinalValGenerator(val_gen, NUM_CLASSES)
    
    cb = [
        keras.callbacks.EarlyStopping('val_loss', patience=12, restore_best_weights=True, verbose=1),
        keras.callbacks.ReduceLROnPlateau('val_loss', factor=0.3, patience=6, min_lr=1e-7, verbose=1),
        CosineLR(LR_HEAD, 1e-6, EPOCHS_HEAD),
        keras.callbacks.ModelCheckpoint(os.path.join(OUTPUT_DIR,'best_head.keras'), 'val_loss', True, 1),
        keras.callbacks.CSVLogger(os.path.join(OUTPUT_DIR,'head_log.csv'))
    ]
    
    history = model.fit(
        train_mix, epochs=EPOCHS_HEAD, validation_data=val_ordinal,
        callbacks=cb, class_weight=class_weights, verbose=1
    )
    return history

# === PHASE 2: FINE-TUNE ===
def fine_tune(model, base, train_gen, val_gen, class_weights):
    print(f"\n[5/7] Phase 2: Fine-tune ({EPOCHS_FINE} ep)...")
    
    for L in base.layers[-UNFREEZE_LAYERS:]:
        L.trainable = True
    for L in base.layers:
        if isinstance(L, keras.layers.BatchNormalization):
            L.trainable = False
    
    trainable = sum(tf.size(w).numpy() for w in model.trainable_weights)
    print(f"  Trainable params: {trainable:,}")
    
    model.compile(
        optimizer=keras.optimizers.AdamW(learning_rate=LR_FINE, weight_decay=WEIGHT_DECAY/10, clipnorm=CLIPNORM),
        loss=CoralOrdinalLoss(num_classes=NUM_CLASSES),
        metrics=['accuracy']
    )
    
    train_mix = MixupGenerator(train_gen, alpha=MIXUP_ALPHA/2)
    val_ordinal = OrdinalValGenerator(val_gen, NUM_CLASSES)
    
    cb = [
        keras.callbacks.EarlyStopping('val_loss', patience=10, restore_best_weights=True, verbose=1),
        keras.callbacks.ReduceLROnPlateau('val_loss', factor=0.5, patience=5, min_lr=1e-8, verbose=1),
        CosineLR(LR_FINE, 1e-8, EPOCHS_FINE),
        keras.callbacks.ModelCheckpoint(os.path.join(OUTPUT_DIR,'best_finetune.keras'), 'val_loss', True, 1),
        keras.callbacks.CSVLogger(os.path.join(OUTPUT_DIR,'fine_log.csv'))
    ]
    
    return model.fit(
        train_mix, epochs=EPOCHS_FINE, validation_data=val_ordinal,
        callbacks=cb, class_weight=class_weights, verbose=1
    )

# === EVALUATE ===
def evaluate(model, val_gen):
    print("\n[6/7] Evaluating...")
    val_ordinal = OrdinalValGenerator(val_gen, NUM_CLASSES)
    preds, trues = [], []
    for _ in range(len(val_ordinal)):
        xb, yb = val_ordinal[_]
        p = model.predict(xb, verbose=0)
        preds.append(p)
        trues.append(yb)
    preds = np.vstack(preds)
    trues = np.vstack(trues)
    
    # Convert ordinal logits to class predictions
    probs = 1 / (1 + np.exp(-preds))  # sigmoid
    pred_idx = (probs > 0.5).sum(axis=1)
    true_idx = (trues > 0.5).sum(axis=1)  # ordinal targets back to class
    
    mae = mean_absolute_error(true_idx, pred_idx)
    acc = (pred_idx == true_idx).mean()
    within1 = (np.abs(pred_idx - true_idx) <= 1).mean()
    
    print(f"  MAE: {mae:.4f} | Exact Acc: {acc:.4f} | Within-1: {within1:.4f}")
    print(classification_report(true_idx, pred_idx, target_names=CLASS_NAMES, digits=4))
    cm = confusion_matrix(true_idx, pred_idx)
    print("Confusion Matrix:")
    print("        ", " ".join(f"{c:>12}" for c in CLASS_NAMES))
    for i, cls in enumerate(CLASS_NAMES):
        print(f"{cls:>10} ", " ".join(f"{cm[i,j]:>12}" for j in range(NUM_CLASSES)))
    
    return acc, mae, within1

# === SAVE & CONVERT ===
def save_artifacts(model, val_acc):
    print("\n[7/7] Saving artifacts...")
    final_path = os.path.join(OUTPUT_DIR, 'model_tbs_ordinal_final.keras')
    model.save(final_path)
    print(f"  Saved: {final_path}")
    
    # Labels
    with open(os.path.join(OUTPUT_DIR, 'labels.txt'), 'w') as f:
        f.write('\n'.join(CLASS_NAMES))
    
    # Save ordinal config for inference
    config = {
        "model_type": "ordinal_coral",
        "num_classes": NUM_CLASSES,
        "class_names": CLASS_NAMES,
        "ordinal_values": ORDINAL_VALUES.tolist(),
        "val_accuracy": float(val_acc)
    }
    with open(os.path.join(OUTPUT_DIR, 'ordinal_config.json'), 'w') as f:
        json.dump(config, f, indent=2)
    
    # TF.js conversion
    try:
        import tensorflowjs as tfjs
        tfjs_dir = os.path.join(OUTPUT_DIR, 'tfjs_ordinal')
        tfjs.converters.save_keras_model(model, tfjs_dir)
        print(f"  TF.js model: {tfjs_dir}")
        
        import shutil
        for dst in ["frontend/public/tfjs_ordinal", "app/src/main/assets/tfjs_ordinal"]:
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(tfjs_dir, dst)
        print(f"  Copied to frontend & Android assets")
    except Exception as e:
        print(f"  TF.js conversion skipped: {e}")

# === MAIN ===
def main():
    print("="*60)
    print("  TBS Ordinal Regression - Target 90%+")
    print("="*60)
    print(f"TF: {tf.__version__} | Keras: {keras.__version__} | GPU: {len(tf.config.list_physical_devices('GPU'))>0}")
    
    train_gen, val_gen = create_generators()
    class_weights = get_class_weights(train_gen)
    model, base = build_model()
    
    train_head(model, train_gen, val_gen, class_weights)
    fine_tune(model, base, train_gen, val_gen, class_weights)
    
    # Load best
    best_path = os.path.join(OUTPUT_DIR, 'best_finetune.keras')
    if os.path.exists(best_path):
        model = keras.models.load_model(best_path, custom_objects={'CoralOrdinalLoss': CoralOrdinalLoss})
    
    val_acc, val_mae, val_within1 = evaluate(model, val_gen)
    save_artifacts(model, val_acc)
    
    print(f"\n{'='*60}")
    print(f"  FINAL: Acc={val_acc:.4f} ({val_acc*100:.2f}%) | MAE={val_mae:.4f} | Within-1={val_within1:.4f}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()