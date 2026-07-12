<#
.SYNOPSIS
  Build & Run TBS Deteksi - Native Android (Gradle)
.DESCRIPTION
  1. Build React frontend -> dist/
  2. Copy dist/ to app/src/main/assets/
  3. Build APK via gradlew
  4. Connect via wireless ADB (optional)
  5. Install debug APK via ADB
  6. Launch app on device
.PARAMETER IPAddress
  Wireless ADB IP (e.g., "192.168.1.100:5555")
.PARAMETER Device
  USB device ID (for multiple devices)
.PARAMETER SkipBuild
  Skip React build
.PARAMETER Reinstall
  Only reinstall APK (skip build)
.EXAMPLE
  .\run.ps1                                    # USB device
  .\run.ps1 -IPAddress "192.168.1.100:5555"   # Wireless
  .\run.ps1 -SkipBuild                         # Skip React build
  .\run.ps1 -Reinstall                         # Reinstall only
#>
param(
    [string]$IPAddress,
    [string]$Device,
    [switch]$SkipBuild,
    [switch]$Reinstall,
    [switch]$NoLaunch
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

# Wireless ADB connect
if ($IPAddress) {
    Write-Host "[0/4] Connect wireless ADB..." -ForegroundColor Cyan
    Write-Host "  Target: $IPAddress" -ForegroundColor Yellow
    
    $connectResult = adb connect $IPAddress 2>&1
    Write-Host "  $connectResult" -ForegroundColor Gray
    
    if ($connectResult -match "connected" -or $connectResult -match "already connected") {
        Write-Host "  Connected OK" -ForegroundColor Green
        $Device = $IPAddress
    } else {
        Write-Host "  WARNING: Connection failed, check IP/port" -ForegroundColor Yellow
        Write-Host "  Tip: Enable Developer Options > Wireless Debugging on phone" -ForegroundColor Gray
    }
    Start-Sleep -Milliseconds 500
}

# Build React
if (-not $SkipBuild -and -not $Reinstall) {
    Write-Host ""
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
if ($Device) { 
    $adbCmd += @("-s", $Device)
    Write-Host "  Device: $Device" -ForegroundColor Gray
}

& $adbCmd uninstall $DEBUG_APP_ID 2>&1 | Out-Null
& $adbCmd uninstall $APP_ID 2>&1 | Out-Null

$apk = ".\app\build\outputs\apk\debug\app-debug.apk"
$installResult = & $adbCmd install -r $apk 2>&1

if ($installResult -match "Success") {
    Write-Host "  Install OK" -ForegroundColor Green
} else {
    Write-Host "  Install result: $installResult" -ForegroundColor Yellow
}

# Launch app
if (-not $NoLaunch) {
    Write-Host ""
    Write-Host "Launching app..." -ForegroundColor Cyan
    & $adbCmd shell am start -n "$APP_ID/.MainActivity" 2>&1 | Out-Null
    Write-Host "App started" -ForegroundColor Green
}

Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host "  SUKSES! Aplikasi ter-install" -ForegroundColor Green
if ($IPAddress) {
    Write-Host "  Device : $IPAddress (wireless)" -ForegroundColor White
}
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host ""
