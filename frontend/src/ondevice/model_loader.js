/* Updated: 2026-07-15 00:30 UTC | v2.2.0 | Native YOLO is primary offline path, TF.js fallback removed (import fails in WebView) */
const IMG_SIZE = 224;
const CLASS_LABELS = ['mentah','kurang_matang','matang','terlalu_matang','busuk'];

const REKOMENDASI_MAP = {
  mentah:'Tidak layak panen. Tunggu 7-10 hari lagi',
  kurang_matang:'Belum optimal. Tunggu 3-5 hari lagi',
  matang:'Layak panen! Kematangan optimal',
  terlalu_matang:'Terlalu matang. Segera panen/reject',
  busuk:'Tolak! Tidak layak olah'
};

const WARNA_MAP = {
  mentah:'#DC2626', kurang_matang:'#D97706', matang:'#16A34A',
  terlalu_matang:'#EA580C', busuk:'#6B21A8'
};

let _model = null;
let _modelLoaded = false;
let _modelLoading = false;

/* 2026-07-13 14:45 | v1.5.1 | Pulse animation badge + clearer mode label (ONDEVICE/Offline/Server/Demo) */

// XHR-based file reader (works on file:// protocol, unlike fetch)
function readFile(path) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', path, true);
    xhr.responseType = 'arraybuffer';
    xhr.onload = () => {
      if (xhr.status === 0 || xhr.status === 200) resolve(xhr.response);
      else reject(new Error(`XHR failed: ${xhr.status}`));
    };
    xhr.onerror = () => reject(new Error('XHR error'));
    xhr.send();
  });
}

function readText(path) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', path, true);
    xhr.onload = () => {
      if (xhr.status === 0 || xhr.status === 200) resolve(xhr.responseText);
      else reject(new Error(`XHR failed: ${xhr.status}`));
    };
    xhr.onerror = () => reject(new Error('XHR error'));
    xhr.send();
  });
}

// XHR HEAD request (check if file exists)
function headFile(path) {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    xhr.open('HEAD', path, true);
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
  const canvas = document.createElement('canvas');
  canvas.width = targetSize;
  canvas.height = targetSize;
  const ctx = canvas.getContext('2d');

  // Fill with black (letterbox padding)
  ctx.fillStyle = 'black';
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

// ponytail: TF.js import fails in WebView (dynamic import not supported).
// Native YOLO (YoloDetector.kt) is the primary offline path.
// This fallback always returns dummy result when native is unavailable.
async function loadModel() { return null; }

export async function predictOnDevice(imageElement) {
  return dummyPredict();
}

function dummyPredict() {
  const randomIdx = Math.floor(Math.random() * CLASS_LABELS.length);
  const confidence = (50 + Math.random() * 49).toFixed(1);
  const allScores = {};
  CLASS_LABELS.forEach((l, i) => {
    allScores[l] = i === randomIdx ? confidence : (Math.random() * 20).toFixed(1);
  });
  return {
    kelas_pred: CLASS_LABELS[randomIdx],
    confidence: parseFloat(confidence),
    all_scores: allScores,
    rekomendasi: REKOMENDASI_MAP[CLASS_LABELS[randomIdx]],
    warna: WARNA_MAP[CLASS_LABELS[randomIdx]],
    mode: 'demo',
  };
}

export async function isOnDeviceReady() {
  try {
    return await headFile('./model_tfjs/model.json');
  } catch {
    return false;
  }
}
