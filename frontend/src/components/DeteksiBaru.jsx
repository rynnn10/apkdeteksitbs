import React, { useState, useRef, useCallback, useEffect } from "react";
import { predictOnDevice, isOnDeviceReady } from "../ondevice/model_loader";

const API_BASE = "";

export default function DeteksiBaru({ onHasil }) {
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("online");
  const [showCamera, setShowCamera] = useState(false);
  const [cameraStream, setCameraStream] = useState(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api");
        if (res.ok) { setMode("online"); return; }
      } catch {}
      const ready = await isOnDeviceReady();
      setMode(ready ? "ondevice" : "dummy");
    })();
  }, []);

  const handleFile = useCallback((file) => {
    if (!file) return;
    setImage(file);
    setPreview(URL.createObjectURL(file));
  }, []);

  const handleUpload = (e) => {
    const file = e.target.files?.[0];
    handleFile(file);
  };

  const openCamera = async () => {
    setShowCamera(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 640 }, height: { ideal: 480 } }
      });
      setCameraStream(stream);
      setTimeout(() => { if (videoRef.current) videoRef.current.srcObject = stream; }, 100);
    } catch (err) {
      alert("Gagal mengakses kamera: " + err.message);
      setShowCamera(false);
    }
  };

  const captureFoto = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob((blob) => {
      handleFile(new File([blob], "foto_tbs.jpg", { type: "image/jpeg" }));
      closeCamera();
    }, "image/jpeg", 0.9);
  };

  const closeCamera = () => {
    if (cameraStream) { cameraStream.getTracks().forEach(t => t.stop()); setCameraStream(null); }
    setShowCamera(false);
  };

  const handlePredict = async () => {
    if (!image) return alert("Pilih atau ambil foto terlebih dahulu!");
    setLoading(true);
    try {
      if (mode === "online") {
        const formData = new FormData();
        formData.append("file", image);
        const res = await fetch(`${API_BASE}/api/predict`, { method: "POST", body: formData });
        if (!res.ok) throw new Error(`Server error: ${res.status}`);
        onHasil(await res.json(), preview);
      } else {
        const img = await blobToImage(image);
        onHasil(await predictOnDevice(img), preview);
      }
    } catch (err) {
      if (mode === "online") {
        try { const img = await blobToImage(image); onHasil(await predictOnDevice(img), preview); } catch {}
      }
      alert("Gagal deteksi: " + err.message);
    } finally { setLoading(false); }
  };

  const modeBadge = () => {
    if (mode === "online") return { text: "Server", color: "#16A34A" };
    if (mode === "ondevice") return { text: "Offline", color: "#D97706" };
    return { text: "Demo", color: "#6B7280" };
  };

  return (
    <div>
      <div style={{ textAlign: "right", marginBottom: 8 }}>
        <span style={{ background: modeBadge().color, color: "#fff", padding: "2px 10px", borderRadius: 10, fontSize: "0.7rem", fontWeight: 600 }}>
          {modeBadge().text.toUpperCase()}
        </span>
      </div>

      <div className="card">
        <h3 className="card-title">Ambil atau Upload Foto TBS</h3>
        {preview ? (
          <div className="upload-zone has-image">
            <img src={preview} alt="Preview TBS" className="preview-img" />
            <p style={{ fontSize: "0.8rem", color: "#6b7280" }}>Foto siap diproses</p>
          </div>
        ) : (
          <div className="upload-zone" onClick={() => fileInputRef.current?.click()}>
            <div className="upload-icon">TBS</div>
            <div className="upload-text">Tap untuk upload foto TBS</div>
            <div className="upload-hint">JPG / PNG, maks 10 MB</div>
          </div>
        )}
        <input ref={fileInputRef} type="file" accept="image/*" capture="environment" onChange={handleUpload} style={{ display: "none" }} />

        <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
          <button className="btn btn-outline" onClick={() => fileInputRef.current?.click()} style={{ flex: 1 }}>Galeri</button>
          <button className="btn btn-outline" onClick={openCamera} style={{ flex: 1 }}>Kamera</button>
        </div>

        {preview && (
          <div style={{ marginTop: 12 }}>
            <button className="btn btn-primary" onClick={handlePredict} disabled={loading}>
              {loading ? (<><div className="spinner" style={{ width: 20, height: 20, borderWidth: 3, margin: 0 }} /> Memproses...</>) : "Deteksi Kematangan"}
            </button>
            <button className="btn btn-danger" onClick={() => { setImage(null); setPreview(null); }} style={{ marginTop: 8 }}>Hapus Foto</button>
          </div>
        )}
      </div>

      <div className="card" style={{ background: "#EFF6FF", fontSize: "0.85rem" }}>
        <strong>Tips:</strong> Pastikan foto TBS jelas, pencahayaan cukup, dan seluruh tandan terlihat dalam frame untuk hasil optimal.
      </div>

      {showCamera && (
        <div className="modal-overlay" onClick={closeCamera}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3 style={{ marginBottom: 8 }}>Ambil Foto TBS</h3>
            <video ref={videoRef} autoPlay playsInline className="camera-view" />
            <canvas ref={canvasRef} style={{ display: "none" }} />
            <div className="camera-actions">
              <button className="btn btn-primary" onClick={captureFoto}>Jepret!</button>
              <button className="btn btn-back" onClick={closeCamera}>Batal</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function blobToImage(blob) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => { resolve(img); URL.revokeObjectURL(url); };
    img.onerror = () => { reject(new Error("Gagal load gambar")); URL.revokeObjectURL(url); };
    img.src = url;
  });
}
