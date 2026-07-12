<#
.SYNOPSIS
  Build & Run TBS Deteksi -- satu klik jalankan full aplikasi
.DESCRIPTION
  Script ini akan:
  1. Cek Python + Node.js
  2. Build frontend (React/Vite --> dist/)
  3. Generate dummy model jika model_tbs.tflite belum ada
  4. Jalankan backend FastAPI (serve frontend + API)
  5. Buka browser ke http://localhost:8000
.PARAMETER Port
  Port untuk server (default: 8000)
.PARAMETER Dev
  Dev mode: API only (frontend dijalankan terpisah via npm run dev)
.PARAMETER SkipBuild
  Skip build frontend (pakai dist/ yang sudah ada)
.PARAMETER SkipModel
  Skip generate dummy model
.PARAMETER NoBrowser
  Jangan buka browser otomatis
.EXAMPLE
  .\run.ps1                           # Full build + run
  .\run.ps1 -SkipBuild                # Tanpa build ulang frontend
  .\run.ps1 -Dev                      # Dev mode, backend API only
  .\run.ps1 -Port 3000                # Port custom
#>
param(
    [int]$Port = 8000,
    [switch]$Dev,
    [switch]$SkipBuild,
    [switch]$SkipModel,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot
$BACKEND = Join-Path $ROOT "backend"
$FRONTEND = Join-Path $ROOT "frontend"
$MODEL_DIR = Join-Path $BACKEND "model_output"
$TFLITE = Join-Path $MODEL_DIR "model_tbs.tflite"

Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host "  TBS DETEKSI KELAPA SAWIT - Build & Run" -ForegroundColor Green
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host ""

# -- 1. Cek Prerequisites
Write-Host "[1/5] Cek prerequisites..." -ForegroundColor Cyan

try {
    $py = python --version 2>&1
    Write-Host "  Python : $py" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Python tidak ditemukan!" -ForegroundColor Red
    exit 1
}

try {
    $node = node --version 2>&1
    Write-Host "  Node   : $node" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Node.js tidak ditemukan!" -ForegroundColor Red
    exit 1
}

# -- 2. Generate Dummy Model (kalau belum ada)
if (-not $SkipModel) {
    if (-not (Test-Path $TFLITE)) {
        Write-Host ""
        Write-Host "[2/5] Model belum ada - generate dummy..." -ForegroundColor Yellow
        Push-Location $BACKEND
        python generate_dummy_model.py
        Pop-Location
        if (Test-Path $TFLITE) {
            Write-Host "  Model generated: $TFLITE" -ForegroundColor Green
        } else {
            Write-Host "  WARNING: Generate dummy model gagal" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[2/5] Model TFLite sudah ada ($TFLITE)" -ForegroundColor Green
    }
} else {
    Write-Host "[2/5] SkipModel - tidak cek model" -ForegroundColor Yellow
}

# -- 3. Build Frontend
if (-not $SkipBuild -and -not $Dev) {
    Write-Host ""
    Write-Host "[3/5] Build frontend (React/Vite)..." -ForegroundColor Cyan
    Push-Location $FRONTEND

    if (-not (Test-Path "node_modules")) {
        Write-Host "  npm install..." -ForegroundColor Yellow
        npm install 2>&1 | Out-Null
    }

    Write-Host "  npm run build..." -ForegroundColor Yellow
    npm run build 2>&1

    $distDir = Join-Path $FRONTEND "dist"
    if (Test-Path $distDir) {
        Write-Host "  Frontend built: $distDir" -ForegroundColor Green
    } else {
        Write-Host "  ERROR: Build frontend gagal!" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Pop-Location
} elseif ($Dev) {
    Write-Host "[3/5] Dev mode - skip build (frontend via npm run dev)" -ForegroundColor Yellow
} else {
    Write-Host "[3/5] SkipBuild - gunakan dist/ yang sudah ada" -ForegroundColor Yellow
}

# -- 4. Install Python deps
Write-Host ""
Write-Host "[4/5] Cek Python dependencies..." -ForegroundColor Cyan
Push-Location $BACKEND
try {
    python -c "import fastapi; import uvicorn; import tensorflow; import PIL" 2>&1 | Out-Null
    Write-Host "  Dependencies OK" -ForegroundColor Green
} catch {
    Write-Host "  Install dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt 2>&1
}
Pop-Location

# -- 5. Jalankan Server
Write-Host ""
Write-Host "[5/5] Start server di port $Port..." -ForegroundColor Cyan
Write-Host ""

if (-not $NoBrowser -and -not $Dev) {
    Start-Process "http://localhost:$Port"
    Start-Sleep 1
}

Push-Location $BACKEND
if ($Dev) {
    Write-Host "=== BACKEND STARTED (DEV MODE) ===" -ForegroundColor Magenta
    Write-Host "Backend : http://localhost:$Port" -ForegroundColor White
    Write-Host "Frontend: http://localhost:3000  (jalankan npm run dev di folder frontend)" -ForegroundColor White
    Write-Host "==================================" -ForegroundColor Magenta
    python main.py --dev
} else {
    Write-Host "=== APLIKASI BERJALAN ===" -ForegroundColor Magenta
    Write-Host "Buka  : http://localhost:$Port" -ForegroundColor White
    Write-Host "Stop  : Ctrl+C" -ForegroundColor White
    Write-Host "=========================" -ForegroundColor Magenta
    $env:APP_PORT = $Port
    python main.py
}
Pop-Location

Write-Host ""
Write-Host "Aplikasi berhenti." -ForegroundColor Yellow
