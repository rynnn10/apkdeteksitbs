#!/usr/bin/env python3
"""
TBS MobileNetV2 Improved - Target 90%+ val_acc
Focal Loss + MixUp + Class Weights + Cosine LR + 2-phase fine-tune
"""
import os, json, numpy as np, tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import classification_report, confusion_matrix

os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

DATASET_DIR = "dataset"
OUTPUT_DIR = "backend/model_output"
IMG_SIZE = (224, 224)
BATCH_SIZE = 32
VAL_SPLIT = 0.2
SEED = 42
EPOCHS_HEAD = 30
EPOCHS_FINE = 25
LR_HEAD = 1e-3
LR_FINE = 5e-6
FOCAL_GAMMA = 2.5
MIXUP_ALPHA = 0.3
CLIPNORM = 1.0
WEIGHT_DECAY = 1e-4
UNFREEZE_LAYERS = 30

CLASS_NAMES = ["mentah", "kurang_matang", "matang", "terlalu_matang", "busuk"]
NUM_CLASSES = len(CLASS_NAMES)

os.makedirs(OUTPUT_DIR, exist_ok=True)

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
        
        b = min(x1.shape[0], x2.shape[0])
        if x1.shape[0] != b:
            x1, y1 = x1[:b], y1[:b]
        if x2.shape[0] != b:
            x2, y2 = x2[:b], y2[:b]
        
        lam = np.random.beta(self.alpha, self.alpha, b).reshape(-1, 1, 1, 1)
        lam_y = np.random.beta(self.alpha, self.alpha, b).reshape(-1, 1)
        
        x = lam * x1 + (1 - lam) * x2
        y = lam_y * y1 + (1 - lam_y) * y2
        return x, y
    
    def on_epoch_end(self):
        self.gen.on_epoch_end()

# === BALANCED GENERATOR (oversample minority) ===
class BalancedGenerator(keras.utils.Sequence):
    def __init__(self, x_set, y_set, batch_size, classes, shuffle=True):
        self.x_set = x_set
        self.y_set = y_set
        self.batch_size = batch_size
        self.classes = classes
        self.shuffle = shuffle
        self.indices = np.arange(len(x_set))
        self.class_indices = {c: np.where(classes == c)[0] for c in np.unique(classes)}
        self.max_class_size = max(len(v) for v in self.class_indices.values())
        self.on_epoch_end()
    
    def __len__(self):
        return int(np.ceil(self.max_class_size * len(self.class_indices) / self.batch_size))
    
    def __getitem__(self, idx):
        batch_x, batch_y = [], []
        for _ in range(self.batch_size):
            c = np.random.choice(list(self.class_indices.keys()))
            i = np.random.choice(self.class_indices[c])
            batch_x.append(self.x_set[i])
            batch_y.append(self.y_set[i])
        return np.array(batch_x), np.array(batch_y)
    
    def on_epoch_end(self):
        if self.shuffle:
            np.random.shuffle(self.indices)

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

# === CLASS WEIGHTS ===
def get_class_weights(generator):
    print("[2/7] Computing class weights...")
    cls_weights = compute_class_weight('balanced', classes=np.unique(generator.classes), y=generator.classes)
    cw_dict = {i: w for i, w in enumerate(cls_weights)}
    print(f"  Weights: {dict(zip(CLASS_NAMES, cls_weights))}")
    return cw_dict

# === BUILD MODEL ===
def build_model():
    print("[3/7] Building MobileNetV2...")
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
    out = layers.Dense(NUM_CLASSES, activation='softmax')(x)
    
    model = keras.Model(inp, out)
    model.compile(
        optimizer=keras.optimizers.AdamW(learning_rate=LR_HEAD, weight_decay=WEIGHT_DECAY, clipnorm=CLIPNORM),
        loss=focal_loss,
        metrics=['accuracy', keras.metrics.TopKCategoricalAccuracy(k=2, name='top2_acc')]
    )
    print(f"  Params: {model.count_params():,}")
    return model, base

# === PHASE 1: HEAD TRAINING ===
def train_head(model, train_gen, val_gen, class_weights):
    print(f"\n[4/7] Phase 1: Head ({EPOCHS_HEAD} ep)...")
    train_mix = MixupGenerator(train_gen, alpha=MIXUP_ALPHA)
    
    cb = [
        keras.callbacks.EarlyStopping('val_loss', patience=10, restore_best_weights=True, verbose=1),
        keras.callbacks.ReduceLROnPlateau('val_loss', factor=0.3, patience=5, min_lr=1e-7, verbose=1),
        CosineLR(LR_HEAD, 1e-6, EPOCHS_HEAD),
        keras.callbacks.ModelCheckpoint(os.path.join(OUTPUT_DIR,'best_head.keras'), 'val_accuracy', True, 1),
        keras.callbacks.CSVLogger(os.path.join(OUTPUT_DIR,'head_log.csv'))
    ]
    return model.fit(train_mix, epochs=EPOCHS_HEAD, validation_data=val_gen,
                     callbacks=cb, class_weight=class_weights, verbose=1)

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
        loss=focal_loss,
        metrics=['accuracy', keras.metrics.TopKCategoricalAccuracy(k=2, name='top2_acc')]
    )
    
    train_mix = MixupGenerator(train_gen, alpha=MIXUP_ALPHA/2)
    
    cb = [
        keras.callbacks.EarlyStopping('val_loss', patience=8, restore_best_weights=True, verbose=1),
        keras.callbacks.ReduceLROnPlateau('val_loss', factor=0.5, patience=4, min_lr=1e-8, verbose=1),
        CosineLR(LR_FINE, 1e-8, EPOCHS_FINE),
        keras.callbacks.ModelCheckpoint(os.path.join(OUTPUT_DIR,'best_finetune.keras'), 'val_accuracy', True, 1),
        keras.callbacks.CSVLogger(os.path.join(OUTPUT_DIR,'fine_log.csv'))
    ]
    return model.fit(train_mix, epochs=EPOCHS_FINE, validation_data=val_gen,
                     callbacks=cb, class_weight=class_weights, verbose=1)

# === EVALUATE ===
def evaluate(model, val_gen):
    print("\n[6/7] Evaluating...")
    val_gen.reset()
    r = model.evaluate(val_gen, verbose=0)
    print(f"  Loss: {r[0]:.4f} | Acc: {r[1]:.4f} | Top-2: {r[2]:.4f}")
    
    p = model.predict(val_gen, verbose=0)
    yp, yt = np.argmax(p, 1), val_gen.classes
    print(classification_report(yt, yp, target_names=CLASS_NAMES, digits=4))
    cm = confusion_matrix(yt, yp)
    print("Confusion Matrix:")
    print("        ", " ".join(f"{c:>12}" for c in CLASS_NAMES))
    for i, cls in enumerate(CLASS_NAMES):
        print(f"{cls:>10} ", " ".join(f"{cm[i,j]:>12}" for j in range(NUM_CLASSES)))
    return r[1]

# === SAVE FINAL & TFJS ===
def save_artifacts(model, val_acc):
    print("\n[7/7] Saving artifacts...")
    final_path = os.path.join(OUTPUT_DIR, f'model_tbs_mobilenetv2_final.keras')
    model.save(final_path)
    print(f"  Saved: {final_path}")
    
    # Save labels
    with open(os.path.join(OUTPUT_DIR, 'labels.txt'), 'w') as f:
        f.write('\n'.join(CLASS_NAMES))
    
    # Convert to TF.js
    try:
        import tensorflowjs as tfjs
        tfjs_dir = os.path.join(OUTPUT_DIR, 'tfjs_model')
        tfjs.converters.save_keras_model(model, tfjs_dir)
        print(f"  TF.js model: {tfjs_dir}")
        
        # Copy to frontend
        import shutil
        frontend_tfjs = "frontend/public/tfjs_model"
        if os.path.exists(frontend_tfjs):
            shutil.rmtree(frontend_tfjs)
        shutil.copytree(tfjs_dir, frontend_tfjs)
        
        assets_tfjs = "app/src/main/assets/tfjs_model"
        if os.path.exists(assets_tfjs):
            shutil.rmtree(assets_tfjs)
        shutil.copytree(tfjs_dir, assets_tfjs)
        print(f"  Copied to frontend & Android assets")
    except Exception as e:
        print(f"  TF.js conversion skipped: {e}")

# === MAIN ===
def main():
    print("="*60)
    print("  TBS MobileNetV2 Improved - Target 90%+")
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
        model = keras.models.load_model(best_path, custom_objects={'FocalLoss': FocalLoss})
    
    val_acc = evaluate(model, val_gen)
    save_artifacts(model, val_acc)
    
    print(f"\n{'='*60}")
    print(f"  FINAL VAL ACCURACY: {val_acc:.4f} ({val_acc*100:.2f}%)")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()