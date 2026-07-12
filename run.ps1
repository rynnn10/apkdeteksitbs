<#
.SYNOPSIS
  Build & Run TBS Deteksi - Native Android (Gradle)
.DESCRIPTION
  1. Build React frontend -> dist/
  2. Copy dist/ to app/src/main/assets/
  3. Build APK via gradlew
  4. Install debug APK via ADB
  5. Launch app on device
.EXAMPLE
  .\run.ps1                  # Full build + install
  .\run.ps1 -SkipBuild       # Skip React build
  .\run.ps1 -Reinstall       # ADB reinstall only
#>
param(
    [switch]$SkipBuild,
    [switch]$Reinstall,
    [switch]$NoBrowser,
    [string]$Device
)

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot
$FRONTEND = Join-Path $ROOT "frontend"
$APP_ASSETS = Join-Path $ROOT "app\src\main\assets"
$APP_ID = "com.tbsdeteksi.kelapa.sawit"
$DEBUG_APP_ID = "$APP_ID.debug"

Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host "  TBS DETEKSI - Native Android Build" -ForegroundColor Green
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host ""

# Build React
if (-not $SkipBuild -and -not $Reinstall) {
    Write-Host "[1/4] Build React frontend..." -ForegroundColor Cyan
    Push-Location $FRONTEND
    
    if (-not (Test-Path "node_modules")) {
        Write-Host "  npm install..." -ForegroundColor Yellow
        npm install 2>&1 | Out-Null
    }
    
    Write-Host "  npm run build..." -ForegroundColor Yellow
    npm run build 2>&1
    
    $dist = Join-Path $FRONTEND "dist"
    if (-not (Test-Path $dist)) {
        Write-Host "  ERROR: Build gagal!" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    
    Pop-Location
    Write-Host "  Build OK" -ForegroundColor Green
} else {
    Write-Host "[1/4] Build skipped" -ForegroundColor Yellow
}

# Copy to assets
if (-not $Reinstall) {
    Write-Host ""
    Write-Host "[2/4] Copy dist/ to assets/" -ForegroundColor Cyan
    
    if (Test-Path $APP_ASSETS) {
        Remove-Item $APP_ASSETS -Recurse -Force
    }
    New-Item -ItemType Directory -Path $APP_ASSETS -Force | Out-Null
    
    $dist = Join-Path $FRONTEND "dist"
    if (Test-Path $dist) {
        Copy-Item "$dist\*" $APP_ASSETS -Recurse -Force
        Write-Host "  Copied OK" -ForegroundColor Green
    }
}

# Gradle build
if (-not $Reinstall) {
    Write-Host ""
    Write-Host "[3/4] Build APK via Gradle..." -ForegroundColor Cyan
    
    & ".\gradlew.bat" assembleDebug
    
    $apk = ".\app\build\outputs\apk\debug\app-debug.apk"
    if (-not (Test-Path $apk)) {
        Write-Host "  ERROR: Gradle build gagal!" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Build OK: $apk" -ForegroundColor Green
}

# Install via ADB
Write-Host ""
Write-Host "[4/4] Install APK..." -ForegroundColor Cyan

$adbCmd = @("adb")
if ($Device) { $adbCmd += @("-s", $Device) }

& $adbCmd uninstall $DEBUG_APP_ID 2>&1 | Out-Null
& $adbCmd uninstall $APP_ID 2>&1 | Out-Null

$apk = ".\app\build\outputs\apk\debug\app-debug.apk"
& $adbCmd install -r $apk

Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host "  SUKSES! Aplikasi ter-install" -ForegroundColor Green
Write-Host "  Launch: adb shell am start -n $APP_ID/.MainActivity" -ForegroundColor White
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host ""
