import React, { useState, useRef, useCallback, useEffect } from "react";
import { predictOnDevice, isOnDeviceReady } from "../ondevice/model_loader";

/* Updated: 2026-07-15 14:10 WIB | v2.2.4 | Bugfix on-device multi-TBS rendering + unknown image server feedback */
const isAndroidWebView =
  typeof window !== "undefined" && window.location.protocol === "file:";

const MODE_OPTIONS = [
  {
    value: "auto",
    label: "Auto",
    desc: "Coba server dulu, fallback ke on-device",
  },
  { value: "server", label: "Server", desc: "Gunakan server laptop" },
  {
    value: "ondevice",
    label: "On-Device",
    desc: "Gunakan AI di HP (YOLO native)",
  },
];

export default function DeteksiBaru({ onHasil }) {
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("loading");
  const [forcedMode, setForcedMode] = useState("auto");
  const [showCamera, setShowCamera] = useState(false);
  const [cameraStream, setCameraStream] = useState(null);
  const [serverIp, setServerIp] = useState("");
  const [showIpInput, setShowIpInput] = useState(false);
  const [showModePicker, setShowModePicker] = useState(false);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const fileInputRef = useRef(null);
  const LOCAL_HISTORY_KEY = "local_detection_history_v1";

  const loadLocalHistory = () => {
    try {
      return JSON.parse(localStorage.getItem(LOCAL_HISTORY_KEY) || "[]");
    } catch {
      return [];
    }
  };

  const persistLocalHistory = (items) => {
    try {
      localStorage.setItem(
        LOCAL_HISTORY_KEY,
        JSON.stringify(items.slice(0, 50)),
      );
    } catch {
      // ignore localStorage failures
    }
  };

  const createThumbnailData = async (file) => {
    try {
      const image = await blobToImage(file);
      const maxSize = 160;
      const ratio = Math.min(maxSize / image.width, maxSize / image.height, 1);
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(image.width * ratio);
      canvas.height = Math.round(image.height * ratio);
      canvas
        .getContext("2d")
        .drawImage(image, 0, 0, canvas.width, canvas.height);
      return canvas.toDataURL("image/jpeg", 0.7);
    } catch {
      return null;
    }
  };

  const saveLocalDetection = async (result, imageFile) => {
    try {
      const thumbnail = await createThumbnailData(imageFile);
      const classes = (result.detections || []).map(
        (d) => d.kelas_pred || "tidak_dikenal",
      );
      const item = {
        id: `local-${Date.now()}`,
        timestamp: new Date().toISOString(),
        kelas: classes.length ? classes.join("|") : "tidak_dikenal",
        confidence: result.detections?.length
          ? Math.max(...result.detections.map((d) => Number(d.confidence) || 0))
          : 0,
        rekomendasi: result.detections?.length
          ? result.detections.map((d) => d.rekomendasi || "").join("; ")
          : "Gambar tidak dikenali sebagai TBS.",
        all_scores: result.detections || [],
        image_data: thumbnail,
        mode: "ondevice",
      };
      const existing = loadLocalHistory();
      persistLocalHistory([item, ...existing]);
    } catch {
      // silent fail
    }
  };

  // Auto-detect mode on mount
  useEffect(() => {
    (async () => {
      // Check saved forced mode
      const savedMode = localStorage.getItem("forced_mode") || "auto";
      setForcedMode(savedMode);

      // Check saved server IP
      const savedIp = localStorage.getItem("server_ip") || "";
      if (savedIp) {
        setServerIp(savedIp);
      }

      // Run auto-detection or forced mode
      const detected = await detectMode(savedMode, savedIp);
      setMode(detected);
    })();
  }, []);

  /**
   * Detect which mode to use based on forced preference and availability
   */
  async function detectMode(forced, savedIp) {
    if (forced === "server" && savedIp) {
      try {
        const res = await fetch(`http://${savedIp}:8000/api`);
        if (res.ok) return "server";
      } catch {}
      // Fall through to check other options
    }

    if (forced === "ondevice") {
      if (isAndroidWebView && window.NativeDetector?.isAvailable?.()) {
        return "ondevice";
      }
      // If native not available, check TF.js
      if (await isOnDeviceReady()) return "ondevice";
      return "offline";
    }

    // Auto mode: try server first
    if (savedIp) {
      try {
        const res = await fetch(`http://${savedIp}:8000/api`);
        if (res.ok) return "server";
      } catch {}
    }

    if (!isAndroidWebView) {
      try {
        const res = await fetch("/api");
        if (res.ok) return "server";
      } catch {}
    }

    // Fallback to on-device
    if (isAndroidWebView && window.NativeDetector?.isAvailable?.()) {
      return "ondevice";
    }
    if (await isOnDeviceReady()) return "ondevice";
    return "offline";
  }

  /**
   * Switch to a new mode manually
   */
  async function switchMode(newForced) {
    setForcedMode(newForced);
    setShowModePicker(false);
    localStorage.setItem("forced_mode", newForced);
    setMode("loading");
    const detected = await detectMode(newForced, serverIp);
    setMode(detected);
  }

  const saveServerIp = () => {
    const ip = serverIp.trim();
    if (!ip) return;
    localStorage.setItem("server_ip", ip);
    // Try connecting
    fetch(`http://${ip}:8000/api`)
      .then((r) => {
        if (r.ok) {
          setMode("server");
          setShowIpInput(false);
        }
      })
      .catch(() => {});
    setShowIpInput(false);
  };

  const getBadgeConfig = () => {
    switch (mode) {
      case "server":
        return {
          label: "SERVER",
          className: "server",
          tip: `Backend: ${serverIp || "localhost"}:8000`,
        };
      case "ondevice":
        return {
          label: "ONDEVICE",
          className: "ondevice",
          tip: "Deteksi YOLO di HP (multi-TBS)",
        };
      case "offline":
        return {
          label: "OFFLINE",
          className: "offline",
          tip: "Model tidak tersedia",
        };
      case "loading":
        return {
          label: "MEMUAT...",
          className: "loading",
          tip: "Menentukan mode deteksi...",
        };
      default:
        return { label: "DEMO", className: "demo", tip: "Mode simulasi" };
    }
  };

  const apiBase =
    mode === "server" && serverIp ? `http://${serverIp}:8000` : "";

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
    if (!navigator.mediaDevices?.getUserMedia) {
      setShowCamera(false);
      fileInputRef.current?.click();
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "environment",
          width: { ideal: 640 },
          height: { ideal: 480 },
        },
      });
      setCameraStream(stream);
      setTimeout(() => {
        if (videoRef.current) videoRef.current.srcObject = stream;
      }, 100);
    } catch (err) {
      setShowCamera(false);
      fileInputRef.current?.click();
    }
  };

  const captureFoto = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob(
      (blob) => {
        handleFile(new File([blob], "foto_tbs.jpg", { type: "image/jpeg" }));
        closeCamera();
      },
      "image/jpeg",
      0.9,
    );
  };

  const closeCamera = () => {
    if (cameraStream) {
      cameraStream.getTracks().forEach((t) => t.stop());
      setCameraStream(null);
    }
    setShowCamera(false);
  };

  const handlePredict = async () => {
    if (!image) return alert("Pilih atau ambil foto terlebih dahulu!");
    setLoading(true);
    try {
      if (mode === "server") {
        // v2.2.3: Server mode — upload via API (handles no_detection)
        const formData = new FormData();
        formData.append("file", image);
        const res = await fetch(`${apiBase}/api/predict`, {
          method: "POST",
          body: formData,
        });
        if (!res.ok) throw new Error(`Server error: ${res.status}`);
        return onHasil(await res.json(), preview);
      }

      // v2.2.3: On-device mode — native YOLO (no dummy fallback on empty detection)
      const img = await blobToImage(image);
      const result = await predictOnDevice(img);
      onHasil(result, preview);
      saveLocalDetection(result, image);
      return;
    } catch (err) {
      // Fallback: if server fails, try on-device
      if (mode === "server") {
        try {
          const img = await blobToImage(image);
          const result = await predictOnDevice(img);
          onHasil(result, preview);
          saveLocalDetection(result, image);
          return;
        } catch {}
      }
      alert(
        "Gagal deteksi: " + (err && err.message ? err.message : String(err)),
      );
    } finally {
      setLoading(false);
    }
  };

  const badge = getBadgeConfig();

  return (
    <div>
      {/* Mode Badge + Settings Row */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
          gap: 8,
        }}
      >
        {/* Mode badge (clickable to change mode) */}
        <div style={{ position: "relative" }}>
          <span
            className={`ai-badge ${badge.className} ai-status-tooltip`}
            data-tip={badge.tip}
            onClick={() => setShowModePicker(!showModePicker)}
            style={{ cursor: "pointer" }}
          >
            <span className="dot" />
            {badge.label}
            <span style={{ marginLeft: 4, fontSize: "0.7rem" }}>▼</span>
          </span>

          {/* Mode picker dropdown */}
          {showModePicker && (
            <div
              style={{
                position: "absolute",
                top: "100%",
                left: 0,
                zIndex: 100,
                background: "#fff",
                border: "1px solid #d1d5db",
                borderRadius: 8,
                boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
                padding: 4,
                minWidth: 200,
                marginTop: 4,
              }}
            >
              {MODE_OPTIONS.map((opt) => (
                <div
                  key={opt.value}
                  onClick={() => switchMode(opt.value)}
                  style={{
                    padding: "8px 12px",
                    cursor: "pointer",
                    borderRadius: 6,
                    background:
                      forcedMode === opt.value ? "#EFF6FF" : "transparent",
                    color: forcedMode === opt.value ? "#2563EB" : "#374151",
                    fontWeight: forcedMode === opt.value ? 600 : 400,
                  }}
                >
                  <div style={{ fontSize: "0.9rem" }}>{opt.label}</div>
                  <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>
                    {opt.desc}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* IP config button (visible always, not just WebView) */}
        <span
          style={{
            cursor: "pointer",
            color: "#2563EB",
            fontSize: "0.8rem",
            textDecoration: "underline",
          }}
          onClick={() => setShowIpInput(true)}
        >
          {serverIp ? `IP: ${serverIp}` : "Atur IP Server"}
        </span>
      </div>

      {/* IP Input Dialog */}
      {showIpInput && (
        <div
          className="card"
          style={{
            background: "#F3F4F6",
            fontSize: "0.85rem",
            padding: "12px",
            marginBottom: 12,
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 6, color: "#374151" }}>
            IP Laptop Server
          </div>
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input
              type="text"
              placeholder="192.168.1.5"
              value={serverIp}
              onChange={(e) => setServerIp(e.target.value)}
              style={{
                flex: 1,
                padding: "6px 10px",
                borderRadius: 6,
                border: "1px solid #d1d5db",
                fontSize: "0.9rem",
              }}
            />
            <button
              onClick={saveServerIp}
              className="btn btn-primary"
              style={{ padding: "6px 14px", fontSize: "0.85rem" }}
            >
              Simpan
            </button>
            <button
              onClick={() => setShowIpInput(false)}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: "#6b7280",
                fontSize: "1.1rem",
              }}
            >
              ✕
            </button>
          </div>
          <div
            style={{
              fontSize: "0.75rem",
              color: "#6b7280",
              marginTop: 4,
            }}
          >
            IP laptop akan tersimpan otomatis. Gunakan mode Server untuk
            koneksi.
          </div>
        </div>
      )}

      {/* Main Upload Card */}
      <div className="card">
        <h3 className="card-title">Ambil atau Upload Foto TBS</h3>
        {preview ? (
          <div className="upload-zone has-image">
            <img src={preview} alt="Preview TBS" className="preview-img" />
            <p style={{ fontSize: "0.8rem", color: "#6b7280" }}>
              Foto siap diproses
            </p>
          </div>
        ) : (
          <div
            className="upload-zone"
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="upload-icon">TBS</div>
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
          style={{ display: "none" }}
        />

        <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
          <button
            className="btn btn-outline"
            onClick={() => fileInputRef.current?.click()}
            style={{ flex: 1 }}
          >
            Galeri
          </button>
          <button
            className="btn btn-outline"
            onClick={openCamera}
            style={{ flex: 1 }}
          >
            Kamera
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
                <>
                  <div
                    className="spinner"
                    style={{
                      width: 20,
                      height: 20,
                      borderWidth: 3,
                      margin: 0,
                    }}
                  />{" "}
                  Memproses...
                </>
              ) : (
                "Deteksi Kematangan"
              )}
            </button>
            <button
              className="btn btn-danger"
              onClick={() => {
                setImage(null);
                setPreview(null);
              }}
              style={{ marginTop: 8 }}
            >
              Hapus Foto
            </button>
          </div>
        )}
      </div>

      <div
        className="card"
        style={{ background: "#EFF6FF", fontSize: "0.85rem" }}
      >
        <strong>Tips:</strong> Pastikan foto TBS jelas, pencahayaan cukup, dan
        seluruh tandan terlihat dalam frame untuk hasil optimal. Mode On-Device
        mendeteksi banyak TBS sekaligus.
      </div>

      {showCamera && (
        <div className="modal-overlay" onClick={closeCamera}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: 8 }}>Ambil Foto TBS</h3>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              className="camera-view"
            />
            <canvas ref={canvasRef} style={{ display: "none" }} />
            <div className="camera-actions">
              <button className="btn btn-primary" onClick={captureFoto}>
                Jepret!
              </button>
              <button className="btn btn-back" onClick={closeCamera}>
                Batal
              </button>
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
    img.onload = () => {
      resolve(img);
      URL.revokeObjectURL(url);
    };
    img.onerror = () => {
      reject(new Error("Gagal load gambar"));
      URL.revokeObjectURL(url);
    };
    img.src = url;
  });
}
