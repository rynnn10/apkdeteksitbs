import React, { useState, useRef, useCallback, useEffect } from "react";
import { predictOnDevice, isOnDeviceReady } from "../ondevice/model_loader";

/* Updated: 2026-07-15 00:30 UTC | v2.2.1 | Fix error message display, TF.js dummy fallback */
const isAndroidWebView = typeof window !== "undefined" && window.location.protocol === "file:";

export default function DeteksiBaru({ onHasil }) {
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("loading");
  const [showCamera, setShowCamera] = useState(false);
  const [cameraStream, setCameraStream] = useState(null);
  const [serverIp, setServerIp] = useState("");
  const [showIpInput, setShowIpInput] = useState(false);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    (async () => {
      // Check if user has saved a server IP
      const savedIp = localStorage.getItem("server_ip") || "";
      if (savedIp) {
        setServerIp(savedIp);
        try {
          const res = await fetch(`http://${savedIp}:8000/api`);
          if (res.ok) { setMode("server"); return; }
        } catch {}
      }
      // Fallback to on-device
      if (isAndroidWebView) {
        try {
          const ready = await isOnDeviceReady();
          setMode(ready ? "ondevice" : "offline");
        } catch { setMode("offline"); }
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

  const saveServerIp = () => {
    const ip = serverIp.trim();
    if (!ip) return;
    localStorage.setItem("server_ip", ip);
    // Try connecting
    fetch(`http://${ip}:8000/api`).then(r => { if (r.ok) setMode("server"); }).catch(() => {});
    setShowIpInput(false);
  };

  const getBadgeConfig = () => {
    switch (mode) {
      case "server": return { label: "SERVER", className: "server", tip: `Backend: ${serverIp || "localhost"}:8000` };
      case "ondevice": return { label: "ONDEVICE", className: "ondevice", tip: "Model AI berjalan di HP (TF.js)" };
      case "offline": return { label: "OFFLINE", className: "offline", tip: "Model tidak ditemukan" };
      case "loading": return { label: "MEMUAT AI...", className: "loading", tip: "Memuat model..." };
      default: return { label: "DEMO", className: "demo", tip: "Mode simulasi acak" };
    }
  };

  const apiBase = mode === "server" && serverIp ? `http://${serverIp}:8000` : isAndroidWebView ? "" : "";

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
      // Priority 1: Native YOLO (offline, bounding box)
      if (window.NativeDetector?.isAvailable?.()) {
        const base64 = await fileToBase64(image);
        let raw;
        try { raw = window.NativeDetector.detect(base64.split(",")[1]); }
        catch (e) { throw new Error("Native error: " + e.message); }
        const dets = JSON.parse(raw);
        onHasil({
          detections: dets.map(d => ({ ...d, all_scores: { [d.kelas_pred]: d.confidence / 100 } })),
          detection_count: dets.length, image_width: 0, image_height: 0,
        }, preview);
      }
      // Priority 2: Server (YOLO via backend)
      else if (mode === "server") {
        const formData = new FormData();
        formData.append("file", image);
        const res = await fetch(`${apiBase}/api/predict`, { method: "POST", body: formData });
        if (!res.ok) throw new Error(`Server error: ${res.status}`);
        onHasil(await res.json(), preview);
      }
      // Priority 3: TF.js classifier (offline)
      else {
        const img = await blobToImage(image);
        onHasil(await predictOnDevice(img), preview);
      }
    } catch (err) {
      if (mode === "server" && !window.NativeDetector?.isAvailable?.()) {
        try { const img = await blobToImage(image); onHasil(await predictOnDevice(img), preview); } catch {}
      }
      alert("Gagal deteksi: " + (err && err.message ? err.message : String(err)));
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

      {isAndroidWebView && (
        <div className="card" style={{ background: "#F3F4F6", fontSize: "0.8rem", padding: "8px 12px" }}>
          {showIpInput ? (
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <input type="text" placeholder="192.168.1.5" value={serverIp} onChange={e => setServerIp(e.target.value)}
                style={{ flex: 1, padding: "4px 8px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: "0.85rem" }} />
              <button onClick={saveServerIp} className="btn btn-primary" style={{ padding: "4px 12px", fontSize: "0.8rem" }}>Simpan</button>
              <button onClick={() => setShowIpInput(false)} style={{ background: "none", border: "none", cursor: "pointer", color: "#6b7280" }}>✕</button>
            </div>
          ) : (
            <span style={{ cursor: "pointer", color: "#2563EB" }} onClick={() => setShowIpInput(true)}>
              {serverIp ? `Server: ${serverIp}:8000 (tap ganti)` : "Tap untuk isi IP server laptop"}
            </span>
          )}
        </div>
      )}

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
