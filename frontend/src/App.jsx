/* 2026-07-14 23:30 UTC | v2.1.2 | Removed broken native YOLO. Hybrid: server/TF.js */
import React, { useState } from 'react';
import DeteksiBaru from './components/DeteksiBaru';
import HasilDeteksi from './components/HasilDeteksi';
import Riwayat from './components/Riwayat';
import Dashboard from './components/Dashboard';

const TABS = ['deteksi', 'riwayat', 'dashboard'];

export default function App() {
  const [activeTab, setActiveTab] = useState('deteksi');
  const [hasil, setHasil] = useState(null);
  const [gambarPreview, setGambarPreview] = useState(null);

  const handleHasil = (data, imageUrl) => {
    setHasil(data);
    setGambarPreview(imageUrl);
    setActiveTab('hasil');
  };

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <h1>🌴 TBS Deteksi</h1>
        <p className="subtitle">Deteksi Kematangan Tandan Buah Segar Kelapa Sawit</p>
      </header>

      {/* Navigation Tabs (sembunyikan 'hasil' dari tabs; muncul otomatis saat deteksi) */}
      {activeTab !== 'hasil' && (
        <nav className="tab-nav">
          <button
            className={`tab-btn ${activeTab === 'deteksi' ? 'active' : ''}`}
            onClick={() => setActiveTab('deteksi')}
          >
            📸 Deteksi Baru
          </button>
          <button
            className={`tab-btn ${activeTab === 'riwayat' ? 'active' : ''}`}
            onClick={() => setActiveTab('riwayat')}
          >
            📋 Riwayat
          </button>
          <button
            className={`tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            📊 Dashboard
          </button>
        </nav>
      )}

      {/* Content */}
      <main className="main-content">
        {activeTab === 'deteksi' && (
          <DeteksiBaru onHasil={handleHasil} />
        )}
        {activeTab === 'hasil' && (
          <HasilDeteksi
            hasil={hasil}
            gambarPreview={gambarPreview}
            onBack={() => setActiveTab('deteksi')}
          />
        )}
        {activeTab === 'riwayat' && <Riwayat />}
        {activeTab === 'dashboard' && <Dashboard />}
      </main>

      {/* Footer */}
      <footer className="footer">
        <p>TBS Deteksi v2.1.2 — Hybrid (Server + TF.js) | 2026-07-14 23:30 UTC</p>
      </footer>
    </div>
  );
}
