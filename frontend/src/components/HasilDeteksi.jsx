/* Updated: 2026-07-15 14:10 WIB | v2.2.4 | Stronger unknown-image UI + bbox normalization support */
import React from "react";

const WARNA_KELAS = {
  mentah: "#DC2626",
  kurang_matang: "#D97706",
  matang: "#16A34A",
  terlalu_matang: "#EA580C",
  busuk: "#6B21A8",
};

/**
 * Normalize score to 0-100 range.
 * - Server sends 0-1 decimal → multiply by 100
 * - Native may send 0-100 already
 */
function normalizeScore(score) {
  if (score === undefined || score === null) return 0;
  const num = Number(score);
  if (num > 1) return Math.min(num, 100); // already percentage
  return num * 100; // convert decimal to percentage
}

function DetectionCard({ det, index }) {
  const kelas_pred = det.kelas_pred || "unknown";
  const kelas_en = det.kelas_en || "";
  const rawConfidence = det.confidence || 0;
  const confidence = normalizeScore(rawConfidence);
  const all_scores = det.all_scores || {};
  const rekomendasi = det.rekomendasi || "";
  const warna = det.warna || WARNA_KELAS[kelas_pred] || "#6b7280";
  const bg_warna = det.bg_warna || warna + "22";
  const icon = det.icon || "";

  // Sort scores, normalize if needed
  const sortedScores = Object.entries(all_scores)
    .map(([k, v]) => [k, normalizeScore(v)])
    .sort((a, b) => b[1] - a[1]);

  const rekomendasiColor =
    kelas_pred === "matang"
      ? "#16A34A"
      : kelas_pred === "kurang_matang"
        ? "#D97706"
        : kelas_pred === "terlalu_matang"
          ? "#EA580C"
          : "#DC2626";

  return (
    <div className="card" style={{ overflow: "hidden", marginBottom: 12 }}>
      <div className="result-header" style={{ backgroundColor: bg_warna }}>
        <div className="result-icon">{icon}</div>
        <div>
          <div
            className="result-label"
            style={{ color: warna, textTransform: "capitalize" }}
          >
            #{index + 1} {kelas_pred.replace("_", " ")}
          </div>
          <div style={{ fontSize: "0.8rem", color: "#6b7280" }}>{kelas_en}</div>
        </div>
        <div className="result-confidence" style={{ color: warna }}>
          {confidence.toFixed(1)}
          <span>%</span>
        </div>
      </div>

      <div
        className="rekomendasi-box"
        style={{ borderLeftColor: rekomendasiColor, background: bg_warna }}
      >
        {rekomendasi}
      </div>

      {sortedScores.length > 0 && (
        <div>
          <h4
            style={{
              fontSize: "0.9rem",
              marginBottom: 10,
              color: "#374151",
            }}
          >
            Confidence Score per Kategori:
          </h4>
          <div className="score-list">
            {sortedScores.map(([kelas, pct]) => {
              const c = WARNA_KELAS[kelas] || "#6b7280";
              return (
                <div className="score-item" key={kelas}>
                  <div className="score-label">{kelas.replace("_", " ")}</div>
                  <div className="score-bar-bg">
                    <div
                      className="score-bar-fill"
                      style={{
                        width: `${pct}%`,
                        backgroundColor: c,
                      }}
                    >
                      {pct > 15 ? `${pct.toFixed(1)}%` : ""}
                    </div>
                  </div>
                  <div className="score-value">{pct.toFixed(1)}%</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function BoundingBoxes({ detections, gambarPreview }) {
  return (
    <div
      style={{ position: "relative", display: "inline-block", width: "100%" }}
    >
      <img
        src={gambarPreview}
        alt="TBS"
        className="preview-img"
        style={{ width: "100%", maxHeight: 300 }}
      />
      {detections.map((det, i) => {
        if (!det.bbox) return null;
        const { x1, y1, x2, y2 } = det.bbox;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${x1 * 100}%`,
              top: `${y1 * 100}%`,
              width: `${(x2 - x1) * 100}%`,
              height: `${(y2 - y1) * 100}%`,
              border: `2.5px solid ${det.warna || "#16A34A"}`,
              borderRadius: 4,
              pointerEvents: "none",
              boxShadow: "0 0 0 1px rgba(255,255,255,0.5)",
            }}
          >
            <span
              style={{
                position: "absolute",
                top: -20,
                left: 0,
                background: det.warna || "#16A34A",
                color: "#fff",
                fontSize: 11,
                fontWeight: 600,
                padding: "1px 6px",
                borderRadius: "3px 3px 3px 0",
                whiteSpace: "nowrap",
                lineHeight: "18px",
              }}
            >
              {det.kelas_pred?.replace("_", " ")}{" "}
              {normalizeScore(det.confidence).toFixed(1)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function HasilDeteksi({ hasil, gambarPreview, onBack }) {
  if (!hasil) return null;

  const detections = hasil.detections || (hasil.kelas_pred ? [hasil] : []);
  const total = detections.length;

  return (
    <div>
      {gambarPreview && (
        <div className="card" style={{ padding: 12 }}>
          <BoundingBoxes
            detections={detections}
            gambarPreview={gambarPreview}
            hasInvalidBbox={detections.some((d) => d.bbox === null)}
          />
        </div>
      )}

      <div
        className="card"
        style={{
          background: "#EFF6FF",
          marginBottom: 12,
          padding: "8px 12px",
          fontSize: "0.9rem",
        }}
      >
        {total > 0 ? (
          <>
            Ditemukan <strong>{total}</strong> TBS dalam gambar
          </>
        ) : (
          <div style={{ textAlign: "center", padding: 20 }}>
            <div style={{ fontSize: "2rem", marginBottom: 8 }}>🔍</div>
            <div
              style={{
                color: "#DC2626",
                fontWeight: 600,
                fontSize: "1.1rem",
                marginBottom: 4,
              }}
            >
              Tidak Ada TBS Terdeteksi
            </div>
            <div style={{ color: "#6b7280", fontSize: "0.85rem" }}>
              Gambar tidak dikenali sebagai Tandan Buah Segar (TBS) kelapa
              sawit.
              <br />
              Pastikan foto jelas, pencahayaan cukup, dan seluruh tandan
              terlihat dalam frame.
              <br />
              Atau coba gunakan mode Server untuk deteksi yang lebih akurat.
            </div>
          </div>
        )}
      </div>

      {detections.map((det, i) => (
        <DetectionCard key={i} det={det} index={i} />
      ))}

      <div style={{ display: "flex", gap: 10 }}>
        <button className="btn btn-back" onClick={onBack} style={{ flex: 1 }}>
          ← Deteksi Baru
        </button>
        <button
          className="btn btn-primary"
          onClick={onBack}
          style={{ flex: 1, fontSize: "0.9rem" }}
        >
          Deteksi Lagi
        </button>
      </div>
    </div>
  );
}
