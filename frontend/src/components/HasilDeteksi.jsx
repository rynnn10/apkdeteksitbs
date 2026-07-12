import React from 'react';

const WARNA_KELAS = {
  mentah: '#DC2626',
  kurang_matang: '#D97706',
  matang: '#16A34A',
  terlalu_matang: '#EA580C',
  busuk: '#6B21A8',
};

export default function HasilDeteksi({ hasil, gambarPreview, onBack }) {
  if (!hasil) return null;

  const { kelas_pred, kelas_en, confidence, all_scores, rekomendasi, warna, bg_warna, icon, kelas_info } = hasil;

  const sortedScores = Object.entries(all_scores || {})
    .sort((a, b) => b[1] - a[1]);

  const rekomendasiColor = kelas_pred === 'matang' ? '#16A34A'
    : kelas_pred === 'kurang_matang' ? '#D97706'
    : kelas_pred === 'terlalu_matang' ? '#EA580C'
    : '#DC2626';

  return (
    <div>
      {/* Preview gambar */}
      {gambarPreview && (
        <div className="card" style={{ padding: 12 }}>
          <img src={gambarPreview} alt="TBS" className="preview-img" style={{ width: '100%', maxHeight: 300 }} />
        </div>
      )}

      {/* Hasil utama */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div className="result-header" style={{ backgroundColor: bg_warna }}>
          <div className="result-icon">{icon}</div>
          <div>
            <div className="result-label" style={{ color: warna, textTransform: 'capitalize' }}>
              {kelas_pred.replace('_', ' ')}
            </div>
            <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>{kelas_en}</div>
          </div>
          <div className="result-confidence" style={{ color: warna }}>
            {confidence}<span>%</span>
          </div>
        </div>

        {/* Rekomendasi */}
        <div className="rekomendasi-box" style={{ borderLeftColor: rekomendasiColor, background: bg_warna }}>
          💬 {rekomendasi}
        </div>

        {/* Score bars semua kelas */}
        <div>
          <h4 style={{ fontSize: '0.9rem', marginBottom: 10, color: '#374151' }}>Confidence Score per Kategori:</h4>
          <div className="score-list">
            {sortedScores.map(([kelas, score]) => {
              const pct = Math.round(score * 100);
              const c = WARNA_KELAS[kelas] || '#6b7280';
              return (
                <div className="score-item" key={kelas}>
                  <div className="score-label">{kelas.replace('_', ' ')}</div>
                  <div className="score-bar-bg">
                    <div
                      className="score-bar-fill"
                      style={{ width: `${pct}%`, backgroundColor: c }}
                    >
                      {pct > 15 ? `${pct}%` : ''}
                    </div>
                  </div>
                  <div className="score-value">{pct}%</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Info semua kelas */}
        {kelas_info && (
          <details style={{ marginTop: 16, fontSize: '0.8rem', color: '#6b7280' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 600, marginBottom: 8 }}>
              📋 Panduan Semua Kategori
            </summary>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {Object.entries(kelas_info).map(([key, info]) => (
                <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{
                    width: 14, height: 14, borderRadius: 4,
                    backgroundColor: info.warna, display: 'inline-block', flexShrink: 0
                  }} />
                  <strong style={{ textTransform: 'capitalize' }}>{key.replace('_', ' ')}:</strong>
                  <span>{info.rekomendasi}</span>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>

      {/* Tombol kembali & deteksi baru */}
      <div style={{ display: 'flex', gap: 10 }}>
        <button className="btn btn-back" onClick={onBack} style={{ flex: 1 }}>
          ← Deteksi Baru
        </button>
        <button className="btn btn-primary" onClick={onBack} style={{ flex: 1, fontSize: '0.9rem' }}>
          📸 Deteksi Lagi
        </button>
      </div>
    </div>
  );
}
