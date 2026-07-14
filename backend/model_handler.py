"""
Load model, preprocess, run inference. Supports YOLO detection + TFLite/Keras classification fallback.

Updated: 2026-07-14 22:30 UTC | v2.1.0
"""
import os
import numpy as np
from PIL import Image

MODEL_DIR = os.path.join(os.path.dirname(__file__), "model_output")
TFLITE_PATH = os.path.join(MODEL_DIR, "model_tbs.tflite")
LABELS_PATH = os.path.join(MODEL_DIR, "labels.txt")
KERAS_PATH = os.path.join(MODEL_DIR, "model_tbs_final.keras")
YOLO_PATH = os.path.join(MODEL_DIR, "yolov8_tbs.pt")

IMG_SIZE = (224, 224)

# ponytail: map Roboflow class names to our internal keys
ROBOFLOW_TO_INTERNAL = {
    "TBS mentah": "mentah", "TBS masak": "matang",
    "Kurang masak": "kurang_matang", "Terlalu masak": "terlalu_matang",
    "TBS abnormal": "busuk", "Janjang kosong": "busuk",
}

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


def _resolve_kelas(label):
    """Map any label to KELAS_INFO key. Handles Roboflow names and unknown labels."""
    if label in KELAS_INFO:
        return label
    if label in ROBOFLOW_TO_INTERNAL:
        return ROBOFLOW_TO_INTERNAL[label]
    # ponytail: unknown label → guess from substring match
    label_lower = label.lower()
    for key in KELAS_INFO:
        if key.replace("_", " ") in label_lower or key[:4] in label_lower:
            return key
    return "mentah"


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
        raise RuntimeError("No classification model found!")

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
        internal_kelas = _resolve_kelas(kelas_pred)
        info = KELAS_INFO[internal_kelas]
        return {
            "bbox": {"x1": 0, "y1": 0, "x2": 1, "y2": 1},
            "kelas_pred": internal_kelas, "kelas_en": info["label_en"],
            "confidence": round(confidence * 100, 2), "all_scores": all_scores,
            "rekomendasi": info["rekomendasi"], "warna": info["warna"],
            "bg_warna": info["bg_warna"], "icon": info["icon"],
        }


class TBSDetector:
    """YOLOv8 object detector with classifier fallback."""

    def __init__(self):
        self.model = None
        self.labels = []
        self._load_labels()
        self._load_model()

    def _load_labels(self):
        if os.path.exists(LABELS_PATH):
            with open(LABELS_PATH, "r") as f:
                self.labels = [line.strip() for line in f.readlines()]
        else:
            self.labels = ["mentah", "kurang_matang", "matang", "terlalu_matang", "busuk"]
        print(f"Detector labels: {self.labels}")

    def _load_model(self):
        if os.path.exists(YOLO_PATH):
            try:
                from ultralytics import YOLO
                self.model = YOLO(YOLO_PATH)
                self.mode = "yolo"
                self.yolo_labels = self.labels
                print(f"YOLOv8 loaded: {YOLO_PATH}")
                return
            except Exception as e:
                print(f"YOLO load failed: {e}")
        # fallback to classifier
        self.classifier = TBSClassifier()
        self.mode = "classifier"
        print("Fallback: using classifier")

    def predict(self, image: Image.Image):
        img_w, img_h = image.size
        if self.mode == "yolo":
            results = self.model(image, verbose=False)
            detections = []
            for box in results[0].boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cls_idx = int(box.cls[0])
                conf = float(box.conf[0])
                kelas = self.yolo_labels[cls_idx] if cls_idx < len(self.yolo_labels) else self.yolo_labels[0]
                internal_kelas = _resolve_kelas(kelas)
                info = KELAS_INFO[internal_kelas]
                detections.append({
                    "bbox": {"x1": round(x1 / img_w, 4), "y1": round(y1 / img_h, 4),
                             "x2": round(x2 / img_w, 4), "y2": round(y2 / img_h, 4)},
                    "kelas_pred": internal_kelas, "kelas_en": info["label_en"],
                    "confidence": round(conf * 100, 2),
                    "all_scores": {internal_kelas: round(conf, 4)},
                    "rekomendasi": info["rekomendasi"], "warna": info["warna"],
                    "bg_warna": info["bg_warna"], "icon": info["icon"],
                })
            return detections, img_w, img_h
        # ponytail: classifier fallback wraps single result as detection
        result = self.classifier.predict(image)
        return [result], img_w, img_h


_detector = None
def get_detector():
    global _detector
    if _detector is None:
        _detector = TBSDetector()
    return _detector
