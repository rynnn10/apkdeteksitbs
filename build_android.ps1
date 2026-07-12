<#
.SYNOPSIS
  Build APK Android untuk TBS Deteksi (Capacitor + React)
.DESCRIPTION
  1. Install frontend dependencies + TFJS
  2. Build React -> dist/
  3. Init & add Android platform (Capacitor)
  4. Sync web assets
  5. Buka Android Studio untuk build APK final
.REQUIREMENTS
  - Node.js 18+
  - Java 17+ (JDK)
  - Android Studio + Android SDK 34+
.EXAMPLE
  .\build_android.ps1
#>
$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot
$FRONTEND = Join-Path $ROOT "frontend"

Write-Host ("=" * 50) -ForegroundColor Green
Write-Host "  BUILD ANDROID APK - TBS Deteksi" -ForegroundColor Green
Write-Host ("=" * 50) -ForegroundColor Green
Write-Host ""

# Cek tooling
Write-Host "[1/4] Cek tooling..." -ForegroundColor Cyan
try { node --version 2>&1 | Out-Null; Write-Host "  Node OK" -ForegroundColor Green }
catch { Write-Host "  Node.js tidak ditemukan!" -ForegroundColor Red; exit 1 }

# Install deps
Write-Host ""
Write-Host "[2/4] Install dependencies..." -ForegroundColor Cyan
Push-Location $FRONTEND
if (-not (Test-Path "node_modules")) { npm install 2>&1; Write-Host "  npm install OK" -ForegroundColor Green }

# Build
Write-Host ""
Write-Host "[3/4] Build frontend..." -ForegroundColor Cyan
npm run build 2>&1
if (Test-Path "dist") { Write-Host "  Build OK: dist/" -ForegroundColor Green }
else { Write-Host "  Build gagal!" -ForegroundColor Red; exit 1 }

# Capacitor
Write-Host ""
Write-Host "[4/4] Init Android (Capacitor)..." -ForegroundColor Cyan
if (-not (Test-Path "capacitor.config.json")) {
    Write-Host "  ERROR: capacitor.config.json tidak ditemukan!" -ForegroundColor Red
    exit 1
}

# Init jika node_modules/@capacitor belum ada
if (-not (Test-Path "node_modules/@capacitor/core")) {
    Write-Host "  Install @capacitor/core + @capacitor/cli..." -ForegroundColor Yellow
    npm install @capacitor/core 2>&1 | Out-Null
    npm install -D @capacitor/cli 2>&1 | Out-Null
}

if (-not (Test-Path "android")) {
    Write-Host "  Init Capacitor..." -ForegroundColor Yellow
    npx cap init TBS_Deteksi com.tbs.deteksi --web-dir=dist 2>&1
}

if (-not (Test-Path "android")) {
    Write-Host "  Add Android platform..." -ForegroundColor Yellow
    npx cap add android 2>&1
}

Write-Host "  Sync web assets..." -ForegroundColor Yellow
npx cap sync android 2>&1

Pop-Location

Write-Host ""
Write-Host ("=" * 50) -ForegroundColor Green
Write-Host "  SELESAI! Buka Android Studio:" -ForegroundColor Green
Write-Host "    cd frontend/android" -ForegroundColor White
Write-Host "    npx cap open android" -ForegroundColor White
Write-Host "  Lalu Build -> Generate Signed Bundle/APK" -ForegroundColor White
Write-Host ("=" * 50) -ForegroundColor Green
Write-Host ""
Write-Host "  ATAU langsung:" -ForegroundColor Yellow
Write-Host "    cd frontend && npx cap open android" -ForegroundColor White
Write-Host ""
