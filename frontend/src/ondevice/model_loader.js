/**
 * On-device inference menggunakan TensorFlow.js + TFLite backend.
 * 
 * Model di-load dari `/model_tfjs/model.json` (dihasilkan dari
 * tensorflowjs_converter). Support 5 kelas TBS.
 * 
 * Fallback: jika model tidak tersedia, return hasil dummy.
 */
const IMG_SIZE = 224;
const TOP_K = 5;

const CLASS_LABELS = [
  'mentah',
  'kurang_matang',
  'matang',
  'terlalu_matang',
  'busuk',
];

const REKOMENDASI_MAP = {
  mentah:          'Tidak layak panen. Tunggu 7-10 hari lagi',
  kurang_matang:   'Belum optimal. Tunggu 3-5 hari lagi',
  matang:          'Layak panen! Kematangan optimal',
  terlalu_matang:  'Terlalu matang. Segera panen/reject',
  busuk:           'Tolak! Tidak layak olah',
};

const WARNA_MAP = {
  mentah:          '#DC2626',
  kurang_matang:   '#D97706',
  matang:          '#16A34A',
  terlalu_matang:  '#EA580C',
  busuk:           '#6B21A8',
};

let _model = null;
let _modelLoaded = false;
let _modelLoading = false;

/**
 * Load TFJS GraphModel dari /model_tfjs/model.json
 */
async function loadModel() {
  if (_modelLoaded) return _model;
  if (_modelLoading) {
    // wait for in-progress load
    let waited = 0;
    while (_modelLoading && waited < 30) {
      await new Promise(r => setTimeout(r, 500));
      waited++;
    }
    return _model;
  }

  _modelLoading = true;
  try {
    const tf = await import('@tensorflow/tfjs');
    await tf.ready();
    console.log('[TFJS] backend:', tf.getBackend());
    
    _model = await tf.loadGraphModel('/model_tfjs/model.json');
    console.log('[TFJS] model loaded from /model_tfjs/model.json');
    _modelLoaded = true;
    return _model;
  } catch (err) {
    console.warn('[TFJS] model load failed, using dummy:', err.message);
    _model = null;
    _modelLoaded = false;
    return null;
  } finally {
    _modelLoading = false;
  }
}

/**
 * Preprocess: canvas/image -> RGB tensor [1,224,224,3] normalized 0-1
 */
async function imageToTensor(imageElement) {
  const tf = await import('@tensorflow/tfjs');
  
  const canvas = document.createElement('canvas');
  canvas.width = IMG_SIZE;
  canvas.height = IMG_SIZE;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(imageElement, 0, 0, IMG_SIZE, IMG_SIZE);

  return tf.tidy(() => {
    const imgTensor = tf.browser.fromPixels(canvas)
      .toFloat()
      .div(255.0);
    return imgTensor.expandDims(0); // [1, 224, 224, 3]
  });
}

/**
 * Inferensi gambar -> hasil klasifikasi
 * @param {HTMLImageElement|HTMLCanvasElement} imageElement
 * @returns {Object} { kelas_pred, confidence, all_scores, rekomendasi, mode }
 */
export async function predictOnDevice(imageElement) {
  const model = await loadModel();

  if (!model) {
    return dummyPredict();
  }

  try {
    const tf = await import('@tensorflow/tfjs');
    const inputTensor = await imageToTensor(imageElement);
    
    const predictions = model.predict(inputTensor);
    const values = await predictions.data();
    const scores = Array.from(values);

    tf.dispose([inputTensor, predictions]);

    const indexed = scores.map((score, i) => ({ idx: i, score }));
    indexed.sort((a, b) => b.score - a.score);

    const topIdx = indexed[0].idx;
    const confidence = (scores[topIdx] * 100).toFixed(1);

    const allScores = {};
    CLASS_LABELS.forEach((label, i) => {
      allScores[label] = (scores[i] * 100).toFixed(1);
    });

    return {
      kelas_pred: CLASS_LABELS[topIdx],
      confidence: parseFloat(confidence),
      all_scores: allScores,
      rekomendasi: REKOMENDASI_MAP[CLASS_LABELS[topIdx]],
      warna: WARNA_MAP[CLASS_LABELS[topIdx]],
      mode: 'ondevice',
    };
  } catch (err) {
    console.error('[TFJS] inference error:', err);
    return dummyPredict();
  }
}

/**
 * Dummy prediction (model belum ada / error)
 */
function dummyPredict() {
  const randomIdx = Math.floor(Math.random() * CLASS_LABELS.length);
  const confidence = (50 + Math.random() * 49).toFixed(1);

  const allScores = {};
  CLASS_LABELS.forEach((label, i) => {
    if (i === randomIdx) {
      allScores[label] = confidence;
    } else {
      allScores[label] = (Math.random() * 20).toFixed(1);
    }
  });

  return {
    kelas_pred: CLASS_LABELS[randomIdx],
    confidence: parseFloat(confidence),
    all_scores: allScores,
    rekomendasi: REKOMENDASI_MAP[CLASS_LABELS[randomIdx]],
    warna: WARNA_MAP[CLASS_LABELS[randomIdx]],
    mode: 'dummy',
  };
}

/**
 * Cek apakah TFJS model tersedia
 */
export async function isOnDeviceReady() {
  try {
    const res = await fetch('/model_tfjs/model.json', { method: 'HEAD' });
    return res.ok;
  } catch {
    return false;
  }
}
