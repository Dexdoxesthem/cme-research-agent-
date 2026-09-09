# CME Futures Research Agent - launcher
# Usage:  .\run-agent.ps1          (start server + open browser)
#         .\run-agent.ps1 -NoBrowser
#         .\run-agent.ps1 -Rebuild
#         .\run-agent.ps1 -Port 9000

param(
    [int]$Port = 8000,
    [switch]$NoBrowser,
    [switch]$Rebuild,
    [switch]$SkipPythonCheck
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyCmd = $env:PYTHON_EXECUTABLE
if (-not $PyCmd) { $PyCmd = 'python' }

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}
function Write-Ok([string]$msg) {
    Write-Host "    $msg" -ForegroundColor Green
}
function Write-Warn([string]$msg) {
    Write-Host "    WARNING: $msg" -ForegroundColor Yellow
}

# ---- 1. Python + deps ----
if (-not $SkipPythonCheck) {
    Write-Step "Checking Python ($PyCmd)"
    try {
        $pyVer = & $PyCmd --version
        Write-Ok "$pyVer"
    } catch {
        Write-Host "Python not found. Install it and add to PATH, or set PYTHON_EXECUTABLE." -ForegroundColor Red
        exit 1
    }

    Write-Step "Checking dependencies"
    try {
        $ok = & $PyCmd -c "import fastapi, uvicorn, yfinance, pandas, numpy; print('ok')" 2>$null
        if ($ok -ne 'ok') { throw 'import check failed' }
        Write-Ok "Dependencies satisfied"
    } catch {
        Write-Warn "Missing dependencies - installing from requirements.txt"
        & $PyCmd -m pip install -r (Join-Path $Root 'requirements.txt')
        if ($LASTEXITCODE -ne 0) { Write-Host "pip install failed." -ForegroundColor Red; exit 1 }
        Write-Ok "Dependencies installed"
    }
}

# ---- 2. Optional frontend rebuild ----
if ($Rebuild) {
    Write-Step "Rebuilding React frontend"
    $frontend = Join-Path $Root 'cme_agent\frontend'
    if (Test-Path (Join-Path $frontend 'package.json')) {
        if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
            Push-Location $frontend
            npm install | Out-Null
            Pop-Location
        }
        Push-Location $frontend
        npm run build
        Pop-Location
        Write-Ok "Frontend rebuilt into cme_agent\dist"
    } else {
        Write-Warn "frontend folder missing - serving existing dist bundle (if any)"
    }
}

# ---- 3. Port check ----
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Write-Warn "Port $Port already in use (PID $($listener.OwningProcess)) - is the server already running?"
    Write-Warn "If it is, open http://127.0.0.1:$Port directly."
}

# ---- 4. Start server ----
Write-Step "Starting server on http://127.0.0.1:$Port"
$serverLog = Join-Path $Root 'server.log'
$serverErr = Join-Path $Root 'server.err.log'
$env:PORT = "$Port"
$proc = Start-Process -FilePath $PyCmd `
    -ArgumentList (Join-Path $Root 'run.py') `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $serverLog `
    -RedirectStandardError $serverErr `
    -WindowStyle Hidden `
    -PassThru

$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $null = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
        $ready = $true
        break
    } catch { }
}
if (-not $ready) {
    Write-Host "Server failed to start. Last log lines:" -ForegroundColor Red
    if (Test-Path $serverErr) { Get-Content $serverErr -Tail 15 }
    elseif (Test-Path $serverLog) { Get-Content $serverLog -Tail 15 }
    exit 1
}

Write-Ok "Server ready (PID $($proc.Id))"
Write-Host ""
Write-Host "  Dashboard:  http://127.0.0.1:$Port" -ForegroundColor Green
Write-Host "  API docs:   http://127.0.0.1:$Port/docs" -ForegroundColor Green
Write-Host "  Log file:   $serverLog" -ForegroundColor DarkGray
Write-Host "  Stop:       Stop-Process -Id $($proc.Id)  (or Ctrl+C in the terminal that owns it)" -ForegroundColor DarkGray
Write-Host ""

# ---- 5. Open browser ----
if (-not $NoBrowser) {
    Write-Step "Opening browser"
    Start-Process "http://127.0.0.1:$Port"
}

Write-Host "Run again with -NoBrowser to skip the browser, or -Port to change the port." -ForegroundColor DarkGray
