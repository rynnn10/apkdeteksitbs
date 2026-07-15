/* Updated: 2026-07-15 14:10 WIB | v2.2.4 | No dummy fallback when YOLO empty + bbox normalization + unknown-image support */
const IMG_SIZE = 224;
const MAX_BBOX_AREA = 0.85; // align with native detector filter to avoid valid large TBS being rejected
const CLASS_LABELS = [
  "mentah",
  "kurang_matang",
  "matang",
  "terlalu_matang",
  "busuk",
];

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

/**
 * Letterbox resize: maintain aspect ratio, pad with black, then crop to 224x224
 * Matches Keras ImageDataGenerator.flow_from_directory(target_size=(224,224))
 */
function letterboxResize(imageElement, targetSize = 224) {
  const canvas = document.createElement("canvas");
  canvas.width = targetSize;
  canvas.height = targetSize;
  const ctx = canvas.getContext("2d");

  // Fill with black (letterbox padding)
  ctx.fillStyle = "black";
  ctx.fillRect(0, 0, targetSize, targetSize);

  const srcW = imageElement.naturalWidth || imageElement.width;
  const srcH = imageElement.naturalHeight || imageElement.height;

  // Calculate scale to fit within target maintaining aspect ratio
  const scale = Math.min(targetSize / srcW, targetSize / srcH);
  const drawW = srcW * scale;
  const drawH = srcH * scale;
  const x = (targetSize - drawW) / 2;
  const y = (targetSize - drawH) / 2;

  ctx.drawImage(imageElement, x, y, drawW, drawH);
  return canvas;
}

/**
 * Check if bounding box is valid (not covering entire image which indicates inference error)
 */
function normalizeBbox(bbox, imgW, imgH) {
  if (!bbox) return null;
  let { x1, y1, x2, y2 } = bbox;
  if (
    [x1, y1, x2, y2].some(
      (v) => v === undefined || v === null || Number.isNaN(v),
    )
  ) {
    return null;
  }

  const maxCoord = Math.max(x1, y1, x2, y2);
  if (maxCoord > 1) {
    const width = imgW || 1;
    const height = imgH || 1;
    x1 = x1 / width;
    y1 = y1 / height;
    x2 = x2 / width;
    y2 = y2 / height;
  }

  const normalized = {
    x1: Math.min(Math.max(x1, 0), 1),
    y1: Math.min(Math.max(y1, 0), 1),
    x2: Math.min(Math.max(x2, 0), 1),
    y2: Math.min(Math.max(y2, 0), 1),
  };

  if (normalized.x2 <= normalized.x1 || normalized.y2 <= normalized.y1) {
    return null;
  }
  const area =
    (normalized.x2 - normalized.x1) * (normalized.y2 - normalized.y1);
  if (area <= 0 || area > MAX_BBOX_AREA) {
    return null;
  }

  return normalized;
}

function isValidBbox(bbox) {
  if (!bbox) return false;
  const { x1, y1, x2, y2 } = bbox;
  const area = (x2 - x1) * (y2 - y1);
  if (area > MAX_BBOX_AREA || area <= 0) return false;
  return true;
}

/**
 * Map a detect result object (from native YOLO or dummy) to full internal format
 * v2.2.4: Normalize absolute bbox coords and clamp 0-1 before rendering
 */
function mapDetection(det, imgW, imgH) {
  const kelas_pred = det.kelas_pred || "mentah";
  const normalizedBbox = normalizeBbox(det.bbox, imgW, imgH);
  return {
    ...det,
    bbox: normalizedBbox,
    kelas_pred,
    kelas_en: KELAS_EN_MAP[kelas_pred] || "Unknown",
    all_scores: det.all_scores || {
      [kelas_pred]: det.confidence ? det.confidence / 100 : 0.5,
    },
    rekomendasi: det.rekomendasi || REKOMENDASI_MAP[kelas_pred] || "",
    warna: det.warna || WARNA_MAP[kelas_pred] || "#6B7280",
    bg_warna: det.bg_warna || BG_WARNA_MAP[kelas_pred] || "#F3F4F6",
    icon: det.icon || ICON_MAP[kelas_pred] || "❓",
    confidence: det.confidence || 0,
  };
}

/**
 * Predict using Native YOLO (Android bridge) - returns array of detections
 */
function predictWithNativeYOLO(imageElement) {
  // Convert image to base64
  const canvas = document.createElement("canvas");
  const imgW = imageElement.naturalWidth || imageElement.width || 1;
  const imgH = imageElement.naturalHeight || imageElement.height || 1;
  canvas.width = imgW;
  canvas.height = imgH;
  canvas.getContext("2d").drawImage(imageElement, 0, 0);
  const base64 = canvas.toDataURL("image/jpeg", 0.9).split(",")[1];

  const raw = window.NativeDetector.detect(base64);
  const rawDetections = JSON.parse(raw || "[]");
  console.log(`[YOLO] Raw detections: ${rawDetections.length}`);

  // Map each detection to full internal format + filter invalid
  const detections = rawDetections
    .map((d) => mapDetection(d, imgW, imgH))
    .filter((d) => d && d.bbox !== null);

  console.log(`[YOLO] Valid detections after filter: ${detections.length}`);
  return detections;
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
 * Returns { detections: [...], detection_count: N, image_width, image_height }
 */
export async function predictOnDevice(imageElement) {
  const imgW = imageElement.naturalWidth || imageElement.width || 0;
  const imgH = imageElement.naturalHeight || imageElement.height || 0;

  // Priority 1: Native YOLO via Android bridge
  if (window.NativeDetector?.isAvailable?.()) {
    try {
      const detections = predictWithNativeYOLO(imageElement);
      // v2.2.3: return empty if YOLO found nothing — DO NOT fallback to dummy
      // This allows the "Tidak Ada TBS Terdeteksi" UI to appear correctly
      return {
        detections,
        detection_count: detections.length,
        image_width: imgW,
        image_height: imgH,
      };
    } catch (e) {
      console.warn("Native YOLO failed:", e);
      // v2.2.3: On native failure, return empty rather than fake dummy data
      return {
        detections: [],
        detection_count: 0,
        image_width: imgW,
        image_height: imgH,
      };
    }
  }

  // Fallback: dummy (single random detection wrapped as array)
  // v2.2.3: Only used when NativeDetector is NOT available at all (dev/browser mode)
  const detections = dummyPredictMulti();
  return {
    detections,
    detection_count: detections.length,
    image_width: imgW,
    image_height: imgH,
  };
}

export async function loadModel() {
  // Native YOLO doesn't need JS model loading
  return null;
}

export async function isOnDeviceReady() {
  // Check if native YOLO is available
  if (window.NativeDetector?.isAvailable?.()) {
    return true;
  }
  // Also check for TF.js model file as fallback indicator
  try {
    return await headFile("./model_tfjs/model.json");
  } catch {
    return false;
  }
}
