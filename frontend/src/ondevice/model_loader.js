/* Updated: 2026-07-12 23:45 | v1.5.0
 * Changed from fetch (broken on file://) to XHR + tf.io.fromMemory
 */
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

async function loadModel() {
  if (_modelLoaded) return _model;
  if (_modelLoading) {
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

    // Read model.json via XHR (works on file://)
    const modelJsonText = await readText('./model_tfjs/model.json');
    const modelConfig = JSON.parse(modelJsonText);

    // Read weight files
    const weightSpecs = modelConfig.weightsManifest[0].weights;
    const weightPaths = modelConfig.weightsManifest[0].paths;
    const weightDataList = [];
    for (const wp of weightPaths) {
      const data = await readFile(`./model_tfjs/${wp}`);
      weightDataList.push(data);
    }

    // Merge weight data
    let totalLength = 0;
    for (const d of weightDataList) totalLength += d.byteLength;
    const mergedWeightData = new Uint8Array(totalLength);
    let offset = 0;
    for (const d of weightDataList) {
      mergedWeightData.set(new Uint8Array(d), offset);
      offset += d.byteLength;
    }

    // Load model from memory (no fetch needed)
    const modelTopology = modelConfig.modelTopology;
    _model = await tf.loadLayersModel(tf.io.fromMemory(
      modelTopology, weightSpecs, mergedWeightData
    ));
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

async function imageToTensor(imageElement) {
  const tf = await import('@tensorflow/tfjs');
  const canvas = document.createElement('canvas');
  canvas.width = IMG_SIZE;
  canvas.height = IMG_SIZE;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(imageElement, 0, 0, IMG_SIZE, IMG_SIZE);
  return tf.tidy(() => {
    return tf.browser.fromPixels(canvas).toFloat().div(255.0).expandDims(0);
  });
}

export async function predictOnDevice(imageElement) {
  const model = await loadModel();
  if (!model) return dummyPredict();

  try {
    const tf = await import('@tensorflow/tfjs');
    const inputTensor = await imageToTensor(imageElement);
    const predictions = model.predict(inputTensor);
    const values = await predictions.data();
    const scores = Array.from(values);
    tf.dispose([inputTensor, predictions]);

    const topIdx = scores.indexOf(Math.max(...scores));
    const confidence = (scores[topIdx] * 100).toFixed(1);
    const allScores = {};
    CLASS_LABELS.forEach((l, i) => { allScores[l] = (scores[i] * 100).toFixed(1); });

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
    mode: 'dummy',
  };
}

export async function isOnDeviceReady() {
  try {
    return await headFile('./model_tfjs/model.json');
  } catch {
    return false;
  }
}
