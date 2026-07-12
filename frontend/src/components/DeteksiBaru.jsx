import React, { useState, useRef, useCallback } from 'react';

const API_BASE = '';

export default function DeteksiBaru({ onHasil }) {
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showCamera, setShowCamera] = useState(false);
  const [cameraStream, setCameraStream] = useState(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const fileInputRef = useRef(null);

  const handleFile = useCallback((file) => {
    if (!file) return;
    setImage(file);
    const url = URL.createObjectURL(file);
    setPreview(url);
  }, []);

  const handleUpload = (e) => {
    const file = e.target.files?.[0];
    handleFile(file);
  };

  const openCamera = async () => {
    setShowCamera(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 640 }, height: { ideal: 480 } }
      });
      setCameraStream(stream);
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      }, 100);
    } catch (err) {
      alert('Gagal mengakses kamera: ' + err.message);
      setShowCamera(false);
    }
  };

  const captureFoto = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    canvas.toBlob((blob) => {
      const file = new File([blob], 'foto_tbs.jpg', { type: 'image/jpeg' });
      handleFile(file);
      closeCamera();
    }, 'image/jpeg', 0.9);
  };

  const closeCamera = () => {
    if (cameraStream) {
      cameraStream.getTracks().forEach(t => t.stop());
      setCameraStream(null);
    }
    setShowCamera(false);
  };

  const handlePredict = async () => {
    if (!image) return alert('Pilih atau ambil foto terlebih dahulu!');
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', image);

      const res = await fetch(`${API_BASE}/api/predict`, { method: 'POST', body: formData });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      onHasil(data, preview);
    } catch (err) {
      alert('Gagal deteksi: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="card">
        <h3 className="card-title">📸 Ambil atau Upload Foto TBS</h3>

        {/* Preview atau upload zone */}
        {preview ? (
          <div className="upload-zone has-image">
            <img src={preview} alt="Preview TBS" className="preview-img" />
            <p style={{ fontSize: '0.8rem', color: '#6b7280' }}>Foto siap diproses</p>
          </div>
        ) : (
          <div
            className="upload-zone"
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="upload-icon">🌴</div>
            <div className="upload-text">Tap untuk upload foto TBS</div>
            <div className="upload-hint">JPG / PNG, maks 10 MB</div>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleUpload}
          style={{ display: 'none' }}
        />

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 10, marginTop: 14 }}>
          <button
            className="btn btn-outline"
            onClick={() => fileInputRef.current?.click()}
            style={{ flex: 1 }}
          >
            🖼️ Galeri
          </button>
          <button
            className="btn btn-outline"
            onClick={openCamera}
            style={{ flex: 1 }}
          >
            📷 Kamera
          </button>
        </div>

        {preview && (
          <div style={{ marginTop: 12 }}>
            <button
              className="btn btn-primary"
              onClick={handlePredict}
              disabled={loading}
            >
              {loading ? (
                <><div className="spinner" style={{ width: 20, height: 20, borderWidth: 3, margin: 0 }} /> Memproses...</>
              ) : '🔍 Deteksi Kematangan'}
            </button>
            <button
              className="btn btn-danger"
              onClick={() => { setImage(null); setPreview(null); }}
              style={{ marginTop: 8 }}
            >
              ✕ Hapus Foto
            </button>
          </div>
        )}
      </div>

      {/* Tips */}
      <div className="card" style={{ background: '#EFF6FF', fontSize: '0.85rem' }}>
        <strong>💡 Tips:</strong> Pastikan foto TBS jelas, pencahayaan cukup, dan seluruh tandan terlihat dalam frame untuk hasil optimal.
      </div>

      {/* Camera Modal */}
      {showCamera && (
        <div className="modal-overlay" onClick={closeCamera}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3 style={{ marginBottom: 8 }}>📷 Ambil Foto TBS</h3>
            <video ref={videoRef} autoPlay playsInline className="camera-view" />
            <canvas ref={canvasRef} style={{ display: 'none' }} />
            <div className="camera-actions">
              <button className="btn btn-primary" onClick={captureFoto}>📸 Jepret!</button>
              <button className="btn btn-back" onClick={closeCamera}>Batal</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
