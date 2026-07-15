/* Updated: Rabu, 15-07-2026 13:10 WIB | v2.5.0 | Fix: stats fetched from relative /api, never resolved inside the APK (file:// origin) — now uses saved server IP */
import React, { useState, useEffect } from "react";
import { getApiBase } from "../lib/apiBase";
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

const WARNA_MAP = {
  mentah: "#DC2626",
  kurang_matang: "#D97706",
  matang: "#16A34A",
  terlalu_matang: "#EA580C",
  busuk: "#6B21A8",
};

const LOCAL_HISTORY_KEY = "local_detection_history_v1";

function loadLocalHistory() {
  try {
    return JSON.parse(localStorage.getItem(LOCAL_HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function buildStatsFromHistory(history) {
  const per_kategori = {};
  const daily = {};
  history.forEach((item) => {
    const kelas = item.kelas || "tidak_dikenal";
    per_kategori[kelas] = (per_kategori[kelas] || 0) + 1;
    const tgl = item.timestamp?.slice(0, 10) || "";
    if (!daily[tgl]) daily[tgl] = {};
    daily[tgl][kelas] = (daily[tgl][kelas] || 0) + 1;
  });
  return {
    total: history.length,
    per_kategori,
    daily,
  };
}

const LABEL_BAHASA = {
  mentah: "Mentah",
  kurang_matang: "Kurang Matang",
  matang: "Matang",
  terlalu_matang: "Terlalu Matang",
  busuk: "Busuk",
};

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const res = await fetch(`${getApiBase()}/api/stats`);
      const serverData = await res.json();
      const localHistory = loadLocalHistory();
      const localStats = buildStatsFromHistory(localHistory);
      const combined = {
        total: (serverData.total || 0) + localStats.total,
        per_kategori: { ...serverData.per_kategori },
        daily: { ...serverData.daily },
      };
      Object.entries(localStats.per_kategori).forEach(([k, v]) => {
        combined.per_kategori[k] = (combined.per_kategori[k] || 0) + v;
      });
      Object.entries(localStats.daily).forEach(([tgl, kelasCounts]) => {
        if (!combined.daily[tgl]) combined.daily[tgl] = {};
        Object.entries(kelasCounts).forEach(([kelas, cnt]) => {
          combined.daily[tgl][kelas] = (combined.daily[tgl][kelas] || 0) + cnt;
        });
      });
      setStats(combined);
    } catch (e) {
      console.error("Gagal fetch stats:", e);
      setStats(
        loadLocalHistory().length
          ? buildStatsFromHistory(loadLocalHistory())
          : null,
      );
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="spinner" />;
  if (!stats || stats.total === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">📊</div>
        <p>Belum ada data untuk dashboard.</p>
        <p style={{ fontSize: "0.8rem" }}>
          Lakukan beberapa deteksi terlebih dahulu.
        </p>
      </div>
    );
  }

  const pieData = Object.entries(stats.per_kategori || {}).map(
    ([name, value]) => ({
      name: LABEL_BAHASA[name] || name,
      value,
      originalName: name,
    }),
  );

  const dailyData = Object.entries(stats.daily || {})
    .map(([tgl, kelasCounts]) => {
      const row = { tgl: tgl?.slice(5) || tgl };
      Object.entries(WARNA_MAP).forEach(([k]) => {
        row[k] = kelasCounts[k] || 0;
      });
      return row;
    })
    .sort((a, b) => a.tgl?.localeCompare?.(b.tgl) || 0);

  return (
    <div>
      <h3 className="card-title">📊 Dashboard Statistik</h3>

      {/* Stat cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-number" style={{ color: "#16A34A" }}>
            {stats.total}
          </div>
          <div className="stat-label">Total Deteksi</div>
        </div>
        {pieData.map((d) => (
          <div className="stat-card" key={d.originalName}>
            <div
              className="stat-number"
              style={{ color: WARNA_MAP[d.originalName] || "#6b7280" }}
            >
              {d.value}
            </div>
            <div className="stat-label">{d.name}</div>
          </div>
        ))}
      </div>

      {/* Pie chart */}
      <div className="card">
        <h4 className="card-title" style={{ fontSize: "0.95rem" }}>
          Distribusi Kematangan TBS
        </h4>
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              outerRadius={90}
              dataKey="value"
              label={({ name, percent }) =>
                `${name} ${(percent * 100).toFixed(0)}%`
              }
            >
              {pieData.map((entry) => (
                <Cell
                  key={entry.originalName}
                  fill={WARNA_MAP[entry.originalName] || "#6b7280"}
                />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Bar chart harian */}
      {dailyData.length > 0 && (
        <div className="card">
          <h4 className="card-title" style={{ fontSize: "0.95rem" }}>
            Tren Harian (7 Hari Terakhir)
          </h4>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={dailyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="tgl" fontSize={10} />
              <YAxis fontSize={10} allowDecimals={false} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: "0.7rem" }} />
              {Object.entries(WARNA_MAP).map(([k, v]) => (
                <Bar
                  key={k}
                  dataKey={k}
                  name={LABEL_BAHASA[k] || k}
                  fill={v}
                  stackId="a"
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <button
        className="btn btn-outline"
        onClick={fetchStats}
        style={{ marginTop: 4 }}
      >
        🔄 Refresh Dashboard
      </button>
    </div>
  );
}
