import React, { useState, useEffect } from "react";

const WARNA_MAP = {
  mentah: { bg: "#FEE2E2", text: "#DC2626" },
  kurang_matang: { bg: "#FEF3C7", text: "#D97706" },
  matang: { bg: "#DCFCE7", text: "#16A34A" },
  terlalu_matang: { bg: "#FFEDD5", text: "#EA580C" },
  busuk: { bg: "#F3E8FF", text: "#6B21A8" },
};

const LOCAL_HISTORY_KEY = "local_detection_history_v1";

function loadLocalHistory() {
  try {
    return JSON.parse(localStorage.getItem(LOCAL_HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

export default function Riwayat() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await fetch("/api/history?limit=50");
      const data = await res.json();
      const local = loadLocalHistory();
      const combined = [...data, ...local].sort((a, b) =>
        (b.timestamp || "").localeCompare(a.timestamp || ""),
      );
      setHistory(combined);
    } catch (e) {
      console.error("Gagal fetch history:", e);
      setHistory(loadLocalHistory());
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (isoStr) => {
    try {
      const d = new Date(isoStr);
      return d.toLocaleString("id-ID", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoStr;
    }
  };

  if (loading) return <div className="spinner" />;

  if (history.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">📭</div>
        <p>Belum ada riwayat deteksi.</p>
        <p style={{ fontSize: "0.8rem" }}>
          Lakukan deteksi untuk melihat hasil di sini.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h3 className="card-title">📋 Riwayat Deteksi ({history.length})</h3>
      <div className="history-list">
        {history.map((item) => {
          const w = WARNA_MAP[item.kelas] || { bg: "#f3f4f6", text: "#374151" };
          return (
            <div className="history-item" key={item.id}>
              {(item.image_data || item.image_path) && (
                <img
                  src={
                    item.image_data ||
                    item.image_path
                      .replace(/\\/g, "/")
                      .replace(/^.*\/uploads\//, "/uploads/")
                  }
                  alt={item.kelas}
                  className="history-thumb"
                  onError={(e) => {
                    e.target.style.display = "none";
                  }}
                />
              )}
              <div className="history-info">
                <div className="history-kelas">
                  {item.kelas.replace("_", " ")}
                </div>
                <div className="history-meta">{formatDate(item.timestamp)}</div>
                <div className="history-meta">{item.rekomendasi}</div>
              </div>
              <span
                className="history-badge"
                style={{ backgroundColor: w.bg, color: w.text }}
              >
                {item.confidence}%
              </span>
            </div>
          );
        })}
      </div>
      <button
        className="btn btn-outline"
        onClick={fetchHistory}
        style={{ marginTop: 12 }}
      >
        🔄 Refresh
      </button>
    </div>
  );
}
