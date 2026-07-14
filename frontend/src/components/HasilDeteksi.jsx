/* Updated: 2026-07-15 00:15 UTC | v2.2.0 | Handle single classification + multi-detection formats */
import React from 'react';

const WARNA_KELAS = {
  mentah: '#DC2626',
  kurang_matang: '#D97706',
  matang: '#16A34A',
  terlalu_matang: '#EA580C',
  busuk: '#6B21A8',
};

function DetectionCard({ det, index }) {
  const kelas_pred = det.kelas_pred || 'unknown';
  const kelas_en = det.kelas_en || '';
  const confidence = det.confidence || 0;
  const all_scores = det.all_scores || {};
  const rekomendasi = det.rekomendasi || '';
  const warna = det.warna || WARNA_KELAS[kelas_pred] || '#6b7280';
  const bg_warna = det.bg_warna || (warna + '22');
  const icon = det.icon || '';
  const sortedScores = Object.entries(all_scores).sort((a, b) => b[1] - a[1]);
  const rekomendasiColor = kelas_pred === 'matang' ? '#16A34A'
    : kelas_pred === 'kurang_matang' ? '#D97706'
    : kelas_pred === 'terlalu_matang' ? '#EA580C'
    : '#DC2626';

  return (
    <div className="card" style={{ overflow: 'hidden', marginBottom: 12 }}>
      <div className="result-header" style={{ backgroundColor: bg_warna }}>
        <div className="result-icon">{icon}</div>
        <div>
          <div className="result-label" style={{ color: warna, textTransform: 'capitalize' }}>
            #{index + 1} {kelas_pred.replace('_', ' ')}
          </div>
          <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>{kelas_en}</div>
        </div>
        <div className="result-confidence" style={{ color: warna }}>
          {confidence}<span>%</span>
        </div>
      </div>

      <div className="rekomendasi-box" style={{ borderLeftColor: rekomendasiColor, background: bg_warna }}>
        {rekomendasi}
      </div>

      {sortedScores.length > 0 && (
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
                    <div className="score-bar-fill" style={{ width: `${pct}%`, backgroundColor: c }}>
                      {pct > 15 ? `${pct}%` : ''}
                    </div>
                  </div>
                  <div className="score-value">{pct}%</div>
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
    <div style={{ position: 'relative', display: 'inline-block', width: '100%' }}>
      <img src={gambarPreview} alt="TBS" className="preview-img" style={{ width: '100%', maxHeight: 300 }} />
      {detections.map((det, i) => {
        if (!det.bbox) return null;
        const { x1, y1, x2, y2 } = det.bbox;
        return (
          <div key={i} style={{
            position: 'absolute',
            left: `${x1 * 100}%`,
            top: `${y1 * 100}%`,
            width: `${(x2 - x1) * 100}%`,
            height: `${(y2 - y1) * 100}%`,
            border: `2.5px solid ${det.warna || '#16A34A'}`,
            borderRadius: 4,
            pointerEvents: 'none',
            boxShadow: '0 0 0 1px rgba(255,255,255,0.5)',
          }}>
            <span style={{
              position: 'absolute', top: -20, left: 0,
              background: det.warna || '#16A34A', color: '#fff',
              fontSize: 11, fontWeight: 600, padding: '1px 6px',
              borderRadius: '3px 3px 3px 0',
              whiteSpace: 'nowrap',
              lineHeight: '18px',
            }}>
              {det.kelas_pred?.replace('_', ' ')} {det.confidence}%
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
          <BoundingBoxes detections={detections} gambarPreview={gambarPreview} />
        </div>
      )}

      {total > 0 && (
        <div className="card" style={{ background: '#EFF6FF', marginBottom: 12, padding: '8px 12px', fontSize: '0.9rem' }}>
          Ditemukan <strong>{total}</strong> TBS dalam gambar
        </div>
      )}

      {detections.map((det, i) => (
        <DetectionCard key={i} det={det} index={i} />
      ))}

      <div style={{ display: 'flex', gap: 10 }}>
        <button className="btn btn-back" onClick={onBack} style={{ flex: 1 }}>
          ← Deteksi Baru
        </button>
        <button className="btn btn-primary" onClick={onBack} style={{ flex: 1, fontSize: '0.9rem' }}>
          Deteksi Lagi
        </button>
      </div>
    </div>
  );
}
