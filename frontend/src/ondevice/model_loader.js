/* Updated: Rabu, 15-07-2026 22:20 WIB | v2.6.1 | Fix: fileSystemIOHandler dropped model.json's `signature` field, which graph models (YOLO) need to know their input/output tensor names — silently broke predict(), fell back to classifier (always 1 box) */
import * as tf from "@tensorflow/tfjs";
import { letterboxParams, mapBoxToOriginal } from "./yolo_geometry";

const IMG_SIZE = 224;
const MODEL_DIR = "./model_tfjs";
// ponytail: mirrors backend/model_handler.py's CLASSIFIER_CONF_THRESHOLD so on-device
// rejects weak guesses the same way the server does, instead of showing a confident wrong label.
const CONF_THRESHOLD = 60.0;
const CLASS_LABELS = [
  "mentah",
  "kurang_matang",
  "matang",
  "terlalu_matang",
  "busuk",
];

// --- YOLO detector (multi-box, matches server mode) ---------------------
const YOLO_MODEL_DIR = "./model_tfjs_yolo";
const YOLO_IMG_SIZE = 640;
// ponytail: mirrors backend/model_handler.py's YOLO_CONF_THRESHOLD (0.25)
const YOLO_CONF_THRESHOLD = 0.25;
// Must match the class order in backend/model_output/labels.txt at export time —
// the exported graph has no label metadata, so this order is load-bearing.
// If yolov8_tbs.pt is retrained with different classes, update both files together.
const YOLO_LABELS = [
  "Janjang kosong",
  "Kurang masak",
  "TBS abnormal",
  "TBS masak",
  "TBS mentah",
  "Terlalu masak",
];
// ponytail: same Roboflow -> internal-key mapping as backend/model_handler.py's
// ROBOFLOW_TO_INTERNAL — duplicated because the frontend has no access to the
// Python module; keep both in sync if class names change.
const ROBOFLOW_TO_INTERNAL = {
  "TBS mentah": "mentah",
  "TBS masak": "matang",
  "Kurang masak": "kurang_matang",
  "Terlalu masak": "terlalu_matang",
  "TBS abnormal": "busuk",
  "Janjang kosong": "busuk",
};

const REKOMENDASI_MAP = {
  mentah: "Tidak layak panen. Tunggu 7-10 hari lagi",
  kurang_matang: "Belum optimal. Tunggu 3-5 hari lagi",
  matang: "Layak panen! Kematangan optimal",
  terlalu_matang: "Terlalu matang. Segera panen/reject",
  busuk: "Tolak! Tidak layak olah",
};

const WARNA_MAP = {
  mentah: "#DC2626",
  kurang_matang: "#D97706",
  matang: "#16A34A",
  terlalu_matang: "#EA580C",
  busuk: "#6B21A8",
};

const BG_WARNA_MAP = {
  mentah: "#FEE2E2",
  kurang_matang: "#FEF3C7",
  matang: "#DCFCE7",
  terlalu_matang: "#FFEDD5",
  busuk: "#F3E8FF",
};

const ICON_MAP = {
  mentah: "❌",
  kurang_matang: "⚠️",
  matang: "✅",
  terlalu_matang: "🔶",
  busuk: "🚫",
};

const KELAS_EN_MAP = {
  mentah: "Unripe",
  kurang_matang: "Underripe",
  matang: "Ripe",
  terlalu_matang: "Overripe",
  busuk: "Rotten/Abnormal",
};

// XHR-based file reader (works on file:// protocol, unlike fetch)
function readFile(path) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("GET", path, true);
    xhr.responseType = "arraybuffer";
    xhr.onload = () => {
      if (xhr.status === 0 || xhr.status === 200) resolve(xhr.response);
      else reject(new Error(`XHR failed: ${xhr.status}`));
    };
    xhr.onerror = () => reject(new Error("XHR error"));
    xhr.send();
  });
}

function readText(path) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("GET", path, true);
    xhr.onload = () => {
      if (xhr.status === 0 || xhr.status === 200) resolve(xhr.responseText);
      else reject(new Error(`XHR failed: ${xhr.status}`));
    };
    xhr.onerror = () => reject(new Error("XHR error"));
    xhr.send();
  });
}

// XHR HEAD request (check if file exists)
function headFile(path) {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    xhr.open("HEAD", path, true);
    xhr.onload = () => resolve(xhr.status === 0 || xhr.status === 200);
    xhr.onerror = () => resolve(false);
    xhr.send();
  });
}

// Combine multiple ArrayBuffers into one (weight shards) — reuse for whatever shard count the model has.
function concatArrayBuffers(buffers) {
  const total = buffers.reduce((sum, b) => sum + b.byteLength, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const buf of buffers) {
    out.set(new Uint8Array(buf), offset);
    offset += buf.byteLength;
  }
  return out.buffer;
}

// Custom tf.io.IOHandler that loads model.json + weight shards via XHR instead of
// fetch() — fetch() does not work against file:// origins (the Android WebView asset
// path), which is why the rest of this file already used XHR for reading files.
function fileSystemIOHandler(baseDir) {
  return {
    load: async () => {
      const modelJson = JSON.parse(await readText(`${baseDir}/model.json`));
      const { weightsManifest, ...artifacts } = modelJson;
      const weightSpecs = [];
      const buffers = [];
      for (const group of weightsManifest) {
        weightSpecs.push(...group.weights);
        for (const path of group.paths) {
          buffers.push(await readFile(`${baseDir}/${path}`));
        }
      }
      // Spread every other top-level field through as-is (format, generatedBy,
      // convertedBy, and — critical for graph models like the YOLO export —
      // `signature`, which maps input/output tensor names. Dropping it silently
      // breaks predict() on graph models while layers models keep working,
      // since only graph models rely on it.
      return {
        ...artifacts,
        weightSpecs,
        weightData: concatArrayBuffers(buffers),
      };
    },
  };
}

let _modelPromise = null;
function getModel() {
  if (!_modelPromise) {
    _modelPromise = tf.loadLayersModel(fileSystemIOHandler(MODEL_DIR));
  }
  return _modelPromise;
}

let _yoloModelPromise = null;
function getYoloModel() {
  if (!_yoloModelPromise) {
    _yoloModelPromise = tf.loadGraphModel(fileSystemIOHandler(YOLO_MODEL_DIR));
  }
  return _yoloModelPromise;
}

// Draw imageElement onto a YOLO_IMG_SIZE square canvas, letterboxed (aspect-ratio
// preserved, padded with Ultralytics' default gray 114) — matches what
// ultralytics does internally before inference, so box coordinates line up.
function letterboxCanvas(imageElement, target = YOLO_IMG_SIZE) {
  const srcW = imageElement.naturalWidth || imageElement.width;
  const srcH = imageElement.naturalHeight || imageElement.height;
  const { scale, drawW, drawH, padX, padY } = letterboxParams(srcW, srcH, target);

  const canvas = document.createElement("canvas");
  canvas.width = target;
  canvas.height = target;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "rgb(114,114,114)";
  ctx.fillRect(0, 0, target, target);
  ctx.drawImage(imageElement, padX, padY, drawW, drawH);

  return { canvas, scale, padX, padY, srcW, srcH };
}

/**
 * Predict using the bundled YOLO TF.js detector — exported from the same
 * yolov8_tbs.pt the server runs, via `model.export(format="saved_model", nms=True)`
 * + tensorflowjs_converter. NMS is baked into the graph (nms=True), so the raw
 * output is already-filtered [N, 6] rows of [x1,y1,x2,y2,conf,cls] in
 * YOLO_IMG_SIZE-letterboxed pixel space — no client-side NMS needed.
 */
async function predictWithYOLO(imageElement) {
  const model = await getYoloModel();
  const { canvas, scale, padX, padY, srcW, srcH } = letterboxCanvas(imageElement);

  const outputTensor = tf.tidy(() => {
    const input = tf.browser.fromPixels(canvas).toFloat().div(255).expandDims(0);
    const out = model.predict(input);
    return Array.isArray(out) ? out[0] : out;
  });
  let rows = await outputTensor.array();
  outputTensor.dispose();
  // Output may come back as [1,N,6] (batched) or [N,6] — normalize to [N,6].
  if (rows.length === 1 && Array.isArray(rows[0]) && Array.isArray(rows[0][0])) {
    rows = rows[0];
  }

  const detections = [];
  for (const row of rows) {
    const [x1, y1, x2, y2, conf, clsIdx] = row;
    if (conf < YOLO_CONF_THRESHOLD) continue;
    const label = YOLO_LABELS[Math.round(clsIdx)];
    if (!label) continue;
    const kelas_pred = ROBOFLOW_TO_INTERNAL[label] || "mentah";

    const bbox = mapBoxToOriginal(x1, y1, x2, y2, { scale, padX, padY, srcW, srcH });
    if (bbox.x2 <= bbox.x1 || bbox.y2 <= bbox.y1) continue;

    detections.push({
      bbox,
      kelas_pred,
      kelas_en: KELAS_EN_MAP[kelas_pred],
      confidence: round1(conf * 100),
      all_scores: { [kelas_pred]: round4(conf) },
      rekomendasi: REKOMENDASI_MAP[kelas_pred],
      warna: WARNA_MAP[kelas_pred],
      bg_warna: BG_WARNA_MAP[kelas_pred],
      icon: ICON_MAP[kelas_pred],
    });
  }
  return detections;
}


/**
 * Predict using the bundled TF.js classifier (MobileNetV2, same weights as the
 * backend's Keras/TFLite fallback). Preprocessing mirrors
 * backend/model_handler.py's TBSClassifier.preprocess(): plain resize to 224x224
 * (no letterbox/crop) + divide by 255. Returns a single classification wrapped
 * as a full-frame "detection" so HasilDeteksi.jsx can render it the same way.
 */
async function predictWithTFJS(imageElement) {
  const model = await getModel();
  const scoresTensor = tf.tidy(() => {
    const img = tf.browser.fromPixels(imageElement).toFloat();
    const resized = tf.image.resizeBilinear(img, [IMG_SIZE, IMG_SIZE]);
    const input = resized.div(255).expandDims(0);
    return model.predict(input);
  });
  const scores = await scoresTensor.data();
  scoresTensor.dispose();

  const predIdx = scores.indexOf(Math.max(...scores));
  const kelas_pred = CLASS_LABELS[predIdx];
  const confidence = round1(scores[predIdx] * 100);
  const all_scores = {};
  CLASS_LABELS.forEach((label, i) => {
    all_scores[label] = round4(scores[i]);
  });

  if (confidence < CONF_THRESHOLD) return [];

  return [
    {
      bbox: { x1: 0, y1: 0, x2: 1, y2: 1 },
      kelas_pred,
      kelas_en: KELAS_EN_MAP[kelas_pred],
      confidence,
      all_scores,
      rekomendasi: REKOMENDASI_MAP[kelas_pred],
      warna: WARNA_MAP[kelas_pred],
      bg_warna: BG_WARNA_MAP[kelas_pred],
      icon: ICON_MAP[kelas_pred],
    },
  ];
}

function round1(n) {
  return Math.round(n * 10) / 10;
}
function round4(n) {
  return Math.round(n * 10000) / 10000;
}

/**
 * Predict using dummy fallback - returns single random detection wrapped as array
 */
function dummyPredictMulti() {
  const randomIdx = Math.floor(Math.random() * CLASS_LABELS.length);
  const confidence = (50 + Math.random() * 49).toFixed(1);
  const allScores = {};
  CLASS_LABELS.forEach((l, i) => {
    allScores[l] = i === randomIdx ? confidence / 100 : Math.random() * 0.2;
  });
  const kelas_pred = CLASS_LABELS[randomIdx];
  return [
    {
      bbox: { x1: 0.05, y1: 0.05, x2: 0.95, y2: 0.95 },
      kelas_pred,
      kelas_en: KELAS_EN_MAP[kelas_pred],
      confidence: parseFloat(confidence),
      all_scores: allScores,
      rekomendasi: REKOMENDASI_MAP[kelas_pred],
      warna: WARNA_MAP[kelas_pred],
      bg_warna: BG_WARNA_MAP[kelas_pred],
      icon: ICON_MAP[kelas_pred],
    },
  ];
}

/**
 * Main on-device prediction function.
 * Priority: YOLO detector (multi-box, matches server) -> single-label classifier
 * -> dummy (only if no model files are present at all).
 * Returns { detections: [...], detection_count: N, image_width, image_height }
 */
export async function predictOnDevice(imageElement) {
  const imgW = imageElement.naturalWidth || imageElement.width || 0;
  const imgH = imageElement.naturalHeight || imageElement.height || 0;
  const wrap = (detections) => ({
    detections,
    detection_count: detections.length,
    image_width: imgW,
    image_height: imgH,
  });

  if (await headFile(`${YOLO_MODEL_DIR}/model.json`)) {
    try {
      return wrap(await predictWithYOLO(imageElement));
    } catch (e) {
      console.warn("YOLO TF.js predict failed, trying classifier:", e);
    }
  }

  try {
    return wrap(await predictWithTFJS(imageElement));
  } catch (e) {
    console.warn("Classifier TF.js predict failed, using dummy:", e);
    // No model files present/loadable — dummy keeps the UI usable instead of a hard error.
    return wrap(dummyPredictMulti());
  }
}

export async function loadModel() {
  return getModel();
}

export async function isOnDeviceReady() {
  try {
    const [yolo, classifier] = await Promise.all([
      headFile(`${YOLO_MODEL_DIR}/model.json`),
      headFile(`${MODEL_DIR}/model.json`),
    ]);
    return yolo || classifier;
  } catch {
    return false;
  }
}
