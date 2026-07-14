"""
Database SQLite untuk menyimpan riwayat deteksi TBS.
Supports multi-detection (YOLO) — stores detections as JSON in all_scores.

Updated: 2026-07-14 15:30 UTC | v2.0.0
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "deteksi_tbs.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            kelas TEXT NOT NULL,
            confidence REAL NOT NULL,
            rekomendasi TEXT NOT NULL,
            all_scores TEXT NOT NULL,
            image_path TEXT,
            latitude REAL,
            longitude REAL
        )
    """)
    conn.commit()
    conn.close()

def save_detection(kelas: str, confidence: float, rekomendasi: str,
                   all_scores: dict, image_path: str = None,
                   latitude: float = None, longitude: float = None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO history (timestamp, kelas, confidence, rekomendasi, all_scores, image_path, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        kelas,
        confidence,
        rekomendasi,
        str(all_scores),
        image_path,
        latitude,
        longitude
    ))
    conn.commit()
    last_id = c.lastrowid
    conn.close()
    return last_id

def get_all_history(limit: int = 50):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM history ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "timestamp": r[1],
            "kelas": r[2],
            "confidence": r[3],
            "rekomendasi": r[4],
            "all_scores": eval(r[5]) if r[5] else {},
            "image_path": r[6],
            "latitude": r[7],
            "longitude": r[8]
        }
        for r in rows
    ]

def get_stats():
    conn = get_connection()
    c = conn.cursor()
    
    # Total per kategori
    c.execute("SELECT kelas, COUNT(*) FROM history GROUP BY kelas")
    per_kategori = dict(c.fetchall())
    
    # Total keseluruhan
    c.execute("SELECT COUNT(*) FROM history")
    total = c.fetchone()[0]

    # Data harian (7 hari terakhir)
    c.execute("""
        SELECT date(timestamp) as tgl, kelas, COUNT(*) 
        FROM history 
        WHERE tgl >= date('now', '-7 days')
        GROUP BY tgl, kelas
        ORDER BY tgl
    """)
    daily_data_raw = c.fetchall()
    
    daily = {}
    for tgl, kelas, cnt in daily_data_raw:
        if tgl not in daily:
            daily[tgl] = {}
        daily[tgl][kelas] = cnt

    conn.close()
    return {
        "total": total,
        "per_kategori": per_kategori,
        "daily": daily
    }
