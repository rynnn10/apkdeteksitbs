"""
Load model TFLite, preprocess gambar, jalankan inference.

Gunakan TFLite runtime (lebih ringan dari TF penuh).
Fallback ke TF jika TFLite gagal.
"""
import os
import numpy as np
from PIL import Image

MODEL_DIR = os.path.join(os.path.dirname(__file__), "model_output")
TFLITE_PATH = os.path.join(MODEL_DIR, "model_tbs.tflite")
LABELS_PATH = os.path.join(MODEL_DIR, "labels.txt")
KERAS_PATH = os.path.join(MODEL_DIR, "model_tbs_final.keras")

IMG_SIZE = (224, 224)

KELAS_INFO = {
    "mentah": {
        "label_id": 0, "label_en": "Unripe",
        "warna": "#DC2626", "bg_warna": "#FEE2E2",
        "rekomendasi": "Tidak layak panen. Tunggu 7-10 hari lagi.", "icon": "❌"
    },
    "kurang_matang": {
        "label_id": 1, "label_en": "Underripe",
        "warna": "#D97706", "bg_warna": "#FEF3C7",
        "rekomendasi": "Belum optimal. Tunggu 3-5 hari lagi.", "icon": "⚠️"
    },
    "matang": {
        "label_id": 2, "label_en": "Ripe",
        "warna": "#16A34A", "bg_warna": "#DCFCE7",
        "rekomendasi": "Layak panen! Kematangan optimal.", "icon": "✅"
    },
    "terlalu_matang": {
        "label_id": 3, "label_en": "Overripe",
        "warna": "#EA580C", "bg_warna": "#FFEDD5",
        "rekomendasi": "Terlalu matang. Segera panen/reject jika brondolan >25%.", "icon": "🔶"
    },
    "busuk": {
        "label_id": 4, "label_en": "Rotten/Abnormal",
        "warna": "#6B21A8", "bg_warna": "#F3E8FF",
        "rekomendasi": "Tolak! TBS busuk/abnormal, tidak layak olah.", "icon": "🚫"
    }
}


class TBSClassifier:
    def __init__(self):
        self.interpreter = None
        self.labels = []
        self._load_labels()
        self._load_model()

    def _load_labels(self):
        if os.path.exists(LABELS_PATH):
            with open(LABELS_PATH, "r") as f:
                self.labels = [line.strip() for line in f.readlines()]
        else:
            self.labels = ["mentah", "kurang_matang", "matang", "terlalu_matang", "busuk"]
        print(f"Labels loaded: {self.labels}")

    def _load_model(self):
        if os.path.exists(TFLITE_PATH):
            try:
                import tensorflow as tf
                self.interpreter = tf.lite.Interpreter(model_path=TFLITE_PATH)
                self.interpreter.allocate_tensors()
                self.input_details = self.interpreter.get_input_details()
                self.output_details = self.interpreter.get_output_details()
                self.mode = "tflite"
                print(f"TFLite model loaded: {TFLITE_PATH}")
                return
            except Exception as e:
                print(f"TFLite load failed: {e}")
        if os.path.exists(KERAS_PATH):
            try:
                import tensorflow as tf
                self.model = tf.keras.models.load_model(KERAS_PATH)
                self.mode = "keras"
                print(f"Keras model loaded: {KERAS_PATH}")
                return
            except Exception as e:
                print(f"Keras load failed: {e}")
        raise RuntimeError("Gagal load model! Pastikan model_tbs.tflite atau model_tbs_final.keras ada di model_output/")

    def preprocess(self, image: Image.Image):
        image = image.resize(IMG_SIZE)
        img_array = np.array(image, dtype=np.float32)
        if img_array.ndim == 2:
            img_array = np.stack([img_array] * 3, axis=-1)
        elif img_array.shape[-1] == 4:
            img_array = img_array[..., :3]
        img_array = img_array / 255.0
        return np.expand_dims(img_array, axis=0)

    def predict(self, image: Image.Image):
        input_data = self.preprocess(image)
        if self.mode == "tflite":
            self.interpreter.set_tensor(self.input_details[0]["index"], input_data)
            self.interpreter.invoke()
            output_data = self.interpreter.get_tensor(self.output_details[0]["index"])
        else:
            output_data = self.model.predict(input_data, verbose=0)

        scores = output_data[0]
        pred_idx = int(np.argmax(scores))
        confidence = float(scores[pred_idx])
        kelas_pred = self.labels[pred_idx] if pred_idx < len(self.labels) else self.labels[0]
        all_scores = {self.labels[i]: round(float(scores[i]), 4) for i in range(len(self.labels))}
        info = KELAS_INFO.get(kelas_pred, KELAS_INFO["mentah"])
        return {
            "kelas_pred": kelas_pred, "kelas_en": info["label_en"],
            "confidence": round(confidence * 100, 2), "all_scores": all_scores,
            "rekomendasi": info["rekomendasi"], "warna": info["warna"],
            "bg_warna": info["bg_warna"], "icon": info["icon"],
            "kelas_info": KELAS_INFO
        }


_classifier = None
def get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = TBSClassifier()
    return _classifier
