<#
.SYNOPSIS
    Starts the backend (FastAPI, port 8001) in one new PowerShell window and the frontend (Vite, port 5173) in another, from the repo root.

.DESCRIPTION
    Run it from anywhere:   .\scripts\start_dev.ps1
    It FIRST checks (and only reports problems, it never installs or downloads anything):
      - the virtual environment .venv and the Python packages the backend needs,
      - Node.js, npm and frontend\node_modules,
      - the processed data the backend loads,
      - that the two ports are free (and who uses them if not).
    Then it opens the two windows, waits until the backend answers /health, and prints the addresses.

.PARAMETER ApiPort   Port of the backend (default 8001).
.PARAMETER WebPort   Port of the frontend (default 5173). The backend only accepts pages from 5173 unless you change cors_origins in api_v2.py.
.PARAMETER Demo      Uses a temporary field-check database (OS_FIELD_DB), so field checks made during a demo are not saved in data\field\field_checks.db.
                     (Plans made in a demo are still saved in data\processed\plans.)
.PARAMETER CheckOnly Only run the checks and print what would be started. Nothing is started.
.PARAMETER Stop      Stops what listens on the two ports and closes the two windows this script opened. Nothing else is started.

.HOW TO STOP
    Press Ctrl+C in each of the two windows and close them, or run:   .\scripts\start_dev.ps1 -Stop
    (-Stop ends whatever listens on the two ports, so do not use it if another program of yours uses them.)
#>
param(
    [int]$ApiPort = 8001,
    [int]$WebPort = 5173,
    [switch]$Demo,
    [switch]$CheckOnly,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot          # the repo root = the folder above scripts\
Set-Location $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Frontend = Join-Path $Root "frontend"
$ApiTitle = "Optimizing Survival - backend (port $ApiPort)"
$WebTitle = "Optimizing Survival - frontend (port $WebPort)"

function Get-Listener([int]$Port) {
    # the process that listens on a TCP port, or $null
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $c) { return $null }
    return Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
}

function Stop-Port([int]$Port) {
    $p = Get-Listener $Port
    if ($null -eq $p) { Write-Host "Port ${Port}: nothing is listening." } else { Write-Host "Port ${Port}: stopping $($p.ProcessName) (id $($p.Id))."; Stop-Process -Id $p.Id -Force }
}

if ($Stop) {
    Stop-Port $ApiPort
    Stop-Port $WebPort
    # close the two windows this script opened: their command line contains their title (also the npm helper process of the frontend)
    Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -and ($_.CommandLine.Contains($ApiTitle) -or $_.CommandLine.Contains($WebTitle) -or $_.CommandLine -match "npm-cli.js.* run dev (-- )?--port $WebPort ") } | ForEach-Object {
        Write-Host "Closing $($_.Name) (id $($_.ProcessId))."
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    return
}

$problems = @()

# ---- the virtual environment and the Python packages
if (-not (Test-Path $Python)) {
    $problems += "The virtual environment is missing ($Python). Create it:  python -m venv .venv   then   .venv\Scripts\python.exe -m pip install -r requirements-day1.txt"
} else {
    $null = & $Python -c "import fastapi, uvicorn, pandas, geopandas, scipy, sklearn, shapely, pyproj" 2>&1
    if ($LASTEXITCODE -ne 0) { $problems += "A Python package the backend needs is missing in .venv. Install them:  .venv\Scripts\python.exe -m pip install -r requirements-day1.txt" }
}

# ---- node, npm and the frontend packages
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { $problems += "Node.js is not installed or not on the PATH (install it from nodejs.org and open a new PowerShell window)." }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { $problems += "npm is not installed or not on the PATH." }
if (-not (Test-Path (Join-Path $Frontend "node_modules"))) { $problems += "frontend\node_modules is missing. Install the frontend packages:  cd frontend; npm install" }

# ---- the data the backend loads
foreach ($f in "data\processed\site_points_clean.csv", "data\processed\species_clean.csv", "data\processed\purpose_scores.csv", "data\processed\scores\site_scores.db", "data\processed\optimizing_survival.db") {
    if (-not (Test-Path (Join-Path $Root $f))) { $problems += "Missing data file $f. See the data pipeline section of README.md." }
}

# ---- the ports
foreach ($pair in @(@("backend", $ApiPort), @("frontend", $WebPort))) {
    $p = Get-Listener $pair[1]
    if ($null -ne $p) { $problems += "Port $($pair[1]) (the $($pair[0])) is already used by $($p.ProcessName) (id $($p.Id)). If it is an old copy, stop it:  Stop-Process -Id $($p.Id)   (or run  .\scripts\start_dev.ps1 -Stop ), or pick another port with -ApiPort / -WebPort." }
}

if ($problems.Count -gt 0) {
    Write-Host ""
    Write-Host "Cannot start yet:" -ForegroundColor Yellow
    $problems | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
    if (-not $CheckOnly) { exit 1 }
    exit 0
}
Write-Host "Checks passed: virtual environment, Python packages, node, frontend packages, data files, free ports." -ForegroundColor Green
if ($CheckOnly) {
    Write-Host "CheckOnly: nothing was started. Backend would be http://localhost:$ApiPort/ , frontend http://localhost:$WebPort/"
    exit 0
}

# ---- the backend window
$envLines = @()
if ($Demo) {
    $demoDb = Join-Path $env:TEMP "optimizing_survival_demo_field_checks.db"
    $envLines += "`$env:OS_FIELD_DB = '$demoDb'"
    Write-Host "Demo mode: field checks go to $demoDb (not to data\field\field_checks.db)."
}
$apiCmd = "`$Host.UI.RawUI.WindowTitle = '$ApiTitle'; Set-Location '$Root'; " + ($envLines -join "; ") + "; & '$Python' -m uvicorn api_v2:app --port $ApiPort"
Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", $apiCmd | Out-Null

# ---- the frontend window (it must know where the backend is)
$webCmd = "`$Host.UI.RawUI.WindowTitle = '$WebTitle'; Set-Location '$Frontend'; `$env:VITE_API_BASE = 'http://127.0.0.1:$ApiPort'; npm.cmd run dev -- --port $WebPort --strictPort"      # npm.cmd, not npm: PowerShell may pick npm.ps1, which a script policy can block
Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", $webCmd | Out-Null

# ---- wait until both answer
Write-Host "Waiting for the backend (it loads the data, about 20 seconds)..."
$api = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 2
    try { $h = Invoke-RestMethod "http://127.0.0.1:$ApiPort/health" -TimeoutSec 3; if ($h.status -eq "ok") { $api = $true; break } } catch { }
}
$web = $false
for ($i = 0; $i -lt 30; $i++) {
    try { $r = Invoke-WebRequest "http://localhost:$WebPort/" -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -eq 200) { $web = $true; break } } catch { Start-Sleep -Seconds 1 }
}

Write-Host ""
if ($api) { Write-Host "Backend  ready: http://localhost:$ApiPort/health   (documentation: http://localhost:$ApiPort/docs)   dataset $($h.dataset_version), hash $($h.dataset_hash)" -ForegroundColor Green } else { Write-Host "Backend did not answer in 2 minutes: look at its window for the error." -ForegroundColor Red }
if ($web) { Write-Host "Frontend ready: http://localhost:$WebPort/   (default page = the new dashboard; the old one is http://localhost:$WebPort/#/legacy)" -ForegroundColor Green } else { Write-Host "Frontend did not answer: look at its window for the error." -ForegroundColor Red }
Write-Host ""
Write-Host "To stop: press Ctrl+C in each of the two windows and close them, or run  .\scripts\start_dev.ps1 -Stop"
