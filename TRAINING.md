# 🤖 Training AI Model TBS Deteksi

## 📂 1. Siapkan Dataset

### Opsi A: Download dari Roboflow
```bash
# 1. Buka https://universe.roboflow.com/search?q=oil+palm+fruit
# 2. Pilih dataset dengan kategori kematangan
# 3. Download format "Folder Structure" atau "Classification"
# 4. Extract ke folder `dataset/`
```

### Opsi B: Buat Dataset Sendiri
```
dataset/
├── mentah/              (50+ foto TBS mentah)
├── kurang_matang/       (50+ foto TBS kurang matang)
├── matang/              (50+ foto TBS matang optimal)
├── terlalu_matang/      (50+ foto TBS terlalu matang)
└── busuk/               (50+ foto TBS busuk/abnormal)
```

**Tips foto:**
- Resolusi min 640x480px
- Pencahayaan baik (outdoor / cahaya alami)
- Fokus pada TBS, background boleh ada
- Variasi angle: depan, samping, atas
- Variasi kondisi: pagi/siang, kering/basah

---

## 🚀 2. Install Dependencies

```powershell
pip install -r requirements-training.txt
```

---

## 🎯 3. Train Model

```powershell
python train_model_tbs.py
```

**Output:**
```
[1/6] Validating dataset...
  ✓ mentah             :   78 images
  ✓ kurang_matang      :   65 images
  ✓ matang             :   92 images
  ✓ terlalu_matang     :   54 images
  ✓ busuk              :   41 images
  
✓ Total: 330 images

[2/6] Creating data generators...
[3/6] Building MobileNetV2 model...
[4/6] Training model...
Epoch 1/20 ...
[5/6] Evaluating model...
[6/6] Saving model...
  ✓ Keras model: backend/model_output/model_tbs_final.keras
  ✓ TFLite model: backend/model_output/model_tbs.tflite
  ✓ Labels: backend/model_output/labels.txt

✓ TRAINING COMPLETE!
```

Training time: ~10-30 menit (tergantung CPU/GPU)

---

## 🧪 4. Test Model

### Test via Backend API:
```powershell
cd backend
python main.py
# Buka http://localhost:8000/docs
# Upload foto TBS di endpoint /predict
```

### Test via APK:
```powershell
# Build APK baru dengan model
.\run.ps1
# Install ke device
# Aplikasi otomatis pakai model TFLite
```

Badge di app akan berubah dari **DEMO** → **OFFLINE** (TFLite inference).

---

## 📱 5. (Opsional) On-Device Web Inference

Jika ingin inference di frontend (TensorFlow.js):

```powershell
# Install tensorflowjs converter
pip install tensorflowjs

# Convert ke TFJS format
python convert_to_tfjs.py

# Copy ke frontend
Copy-Item model_tfjs -Destination frontend\public\ -Recurse

# Rebuild APK
.\run.ps1
```

Badge akan jadi **ONDEVICE**.

---

## ⚙️ Tuning Hyperparameter

Edit `train_model_tbs.py`:

```python
BATCH_SIZE = 32        # 16/32/64 - lebih kecil = stabil, lebih besar = cepat
EPOCHS = 20            # 15-30 epoch cukup
LEARNING_RATE = 0.001  # 0.0001-0.01
```

Untuk akurasi lebih tinggi:
- Tambah data (min 100 foto per kelas)
- Augmentasi data lebih agresif
- Fine-tune base model (set `base_model.trainable = True`)

---

## 🎓 Training Best Practices

1. **Balance dataset** - jumlah foto per kelas sebisa mungkin sama
2. **Validation split** - 20% data untuk validasi (sudah di-set)
3. **Early stopping** - training berhenti otomatis jika overfitting
4. **Data augmentation** - sudah di-set (rotation, flip, zoom, brightness)
5. **Monitor accuracy** - target min 85% validation accuracy untuk production

---

## 📊 Expected Results

| Dataset Size | Training Time | Expected Accuracy |
|--------------|---------------|-------------------|
| 100-200 img  | 5-10 min      | 70-80%            |
| 200-500 img  | 10-20 min     | 80-90%            |
| 500-1000 img | 20-40 min     | 90-95%            |

Accuracy <70% → tambah data atau cek kualitas label.

---

**Last updated:** 2026-07-12 10:59 UTC  
**Version:** 1.0.4
