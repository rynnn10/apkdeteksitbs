import React, { useState, useRef, useCallback, useEffect } from "react";
import { predictOnDevice, isOnDeviceReady } from "../ondevice/model_loader";

// 2026-07-13 14:35 | v1.5.1 | AI badge: ONDEVICE/Server/Offline/Demo + pulse animation + loading state
// In APK (file://), no proxy available — backend reachable via LAN IP
// Default: try on-device inference first, fallback dummy
const isAndroidWebView = typeof window !== "undefined" && window.location.protocol === "file:";
const API_BASE = isAndroidWebView ? "" : "";

export default function DeteksiBaru({ onHasil }) {
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("loading");
  const [showCamera, setShowCamera] = useState(false);
  const [cameraStream, setCameraStream] = useState(null);
  const [modelLoadError, setModelLoadError] = useState(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    (async () => {
      if (isAndroidWebView) {
        try {
          const ready = await isOnDeviceReady();
          setMode(ready ? "ondevice" : "offline");
        } catch {
          setMode("offline");
        }
        return;
      }
      try {
        const res = await fetch("/api");
        if (res.ok) { setMode("server"); return; }
      } catch {}
      const ready = await isOnDeviceReady();
      setMode(ready ? "ondevice" : "offline");
    })();
  }, []);

  const getBadgeConfig = () => {
    switch (mode) {
      case "server": return { label: "SERVER", className: "server", tip: "Menghubungkan ke backend FastAPI" };
      case "ondevice": return { label: "ONDEVICE", className: "ondevice", tip: "Model AI berjalan di HP (TF.js)" };
      case "offline": return { label: "OFFLINE", className: "offline", tip: "Model tidak ditemukan, cek assets/model_tfjs" };
      case "loading": return { label: "MEMUAT AI...", className: "loading", tip: "Memuat model TensorFlow.js..." };
      default: return { label: "DEMO", className: "demo", tip: "Mode simulasi acak (model gagal load)" };
    }
  };

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
      if (isAndroidWebView && window.NativeDetector?.isAvailable?.()) {
        // ponytail: native YOLO TFLite via JS bridge
        const base64 = await fileToBase64(image);
        const raw = window.NativeDetector.detect(base64.split(",")[1]);
        const dets = JSON.parse(raw);
        const result = {
          detections: dets.map(d => ({ ...d, all_scores: { [d.kelas_pred]: d.confidence / 100 } })),
          detection_count: dets.length,
          image_width: 0, image_height: 0,
        };
        onHasil(result, preview);
      } else if (mode === "server") {
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
      if (mode === "server") {
        try { const img = await blobToImage(image); onHasil(await predictOnDevice(img), preview); } catch {}
      }
      alert("Gagal deteksi: " + err.message);
    } finally { setLoading(false); }
  };

  const badge = getBadgeConfig();

  return (
    <div>
      <div style={{ textAlign: "right", marginBottom: 8 }}>
        <span className={`ai-badge ${badge.className} ai-status-tooltip`} data-tip={badge.tip}>
          <span className="dot" />
          {badge.label}
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

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
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
