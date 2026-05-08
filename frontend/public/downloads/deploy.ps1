# =============================================================================
# Tile Station — One-Click Manual Deploy
# =============================================================================
# Double-click this file (after right-click → Run with PowerShell) to:
#   1. Download the latest code zip from Emergent preview
#   2. Extract it to C:\TileStation
#   3. Deploy backend  → Tile-Station service on Railway
#   4. Deploy frontend → carefree-friendship service on Railway
#
# Pre-requisites (one-time, only do once):
#   1. Install Node.js LTS:        https://nodejs.org
#   2. Open PowerShell and run:    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
#   3. Install Railway CLI:        npm install -g @railway/cli
#   4. Login to Railway:           railway login
#
# How to run:
#   - Save this file somewhere convenient, e.g. Desktop
#   - Right-click → Run with PowerShell
#   - Wait ~5–10 minutes for both services to deploy
# =============================================================================

$ErrorActionPreference = "Stop"

$DEPLOY_DIR  = "C:\TileStation"
$ZIP_URL     = "https://feature-verification-7.preview.emergentagent.com/downloads/tilestation-latest.zip"
$ZIP_PATH    = "$DEPLOY_DIR\tilestation-latest.zip"
$BACKEND_DIR = "$DEPLOY_DIR\backend"
$FRONTEND_DIR = "$DEPLOY_DIR\frontend"

function Step($n, $msg) {
    Write-Host ""
    Write-Host "==[ Step $n ]==> $msg" -ForegroundColor Cyan
}

function Ok($msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}

function Fail($msg) {
    Write-Host "  [FAIL] $msg" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# ---------------------------------------------------------------------------
# Step 0 — Sanity checks
# ---------------------------------------------------------------------------
Step 0 "Checking prerequisites"
try {
    $rwVer = railway --version 2>&1
    Ok "Railway CLI: $rwVer"
} catch {
    Fail "Railway CLI not installed. Run: npm install -g @railway/cli"
}

# ---------------------------------------------------------------------------
# Step 1 — Wipe old deploy folder, recreate
# ---------------------------------------------------------------------------
Step 1 "Cleaning $DEPLOY_DIR"
if (Test-Path $DEPLOY_DIR) {
    Remove-Item -Path $DEPLOY_DIR -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -Path $DEPLOY_DIR -ItemType Directory -Force | Out-Null
Ok "Folder ready"

# ---------------------------------------------------------------------------
# Step 2 — Download latest code zip
# ---------------------------------------------------------------------------
Step 2 "Downloading latest code from Emergent preview"
try {
    Invoke-WebRequest -Uri $ZIP_URL -OutFile $ZIP_PATH -UseBasicParsing
    $sizeMB = [math]::Round((Get-Item $ZIP_PATH).Length / 1MB, 1)
    Ok "Downloaded $sizeMB MB"
} catch {
    Fail "Could not download zip: $_"
}

# ---------------------------------------------------------------------------
# Step 3 — Extract zip
# ---------------------------------------------------------------------------
Step 3 "Extracting code"
try {
    Expand-Archive -Path $ZIP_PATH -DestinationPath $DEPLOY_DIR -Force
    Remove-Item $ZIP_PATH -Force
    if (-not (Test-Path $BACKEND_DIR))  { Fail "Extracted but no backend/ folder found" }
    if (-not (Test-Path $FRONTEND_DIR)) { Fail "Extracted but no frontend/ folder found" }
    Ok "Extracted to $DEPLOY_DIR"
} catch {
    Fail "Extraction failed: $_"
}

# ---------------------------------------------------------------------------
# Step 4 — Deploy backend (Tile-Station service)
# ---------------------------------------------------------------------------
Step 4 "Deploying backend → Tile-Station service"
Push-Location $BACKEND_DIR
try {
    # Re-link in case the link was lost between sessions. Non-interactive:
    # if Railway can resolve the service from a cached link, this is silent;
    # otherwise it surfaces the picker. The user already linked once during
    # initial setup so usually this is silent.
    railway link --project fabulous-nature --service Tile-Station --environment production 2>&1 | Out-Host
    railway up --detach 2>&1 | Out-Host
    Ok "Backend deploy queued. Watch logs in Railway dashboard."
} catch {
    Pop-Location
    Fail "Backend deploy failed: $_"
}
Pop-Location

# ---------------------------------------------------------------------------
# Step 5 — Deploy frontend (carefree-friendship service)
# ---------------------------------------------------------------------------
Step 5 "Deploying frontend → carefree-friendship service"
Push-Location $FRONTEND_DIR
try {
    railway link --project fabulous-nature --service carefree-friendship --environment production 2>&1 | Out-Host
    railway up --detach 2>&1 | Out-Host
    Ok "Frontend deploy queued. Watch logs in Railway dashboard."
} catch {
    Pop-Location
    Fail "Frontend deploy failed: $_"
}
Pop-Location

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " DEPLOY DONE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host " Backend logs:  https://railway.com/project/3e35e5bf-583b-4389-be71-c0a68a2f1d6f"
Write-Host " Frontend live: https://tilestation.co.uk"
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to close"
