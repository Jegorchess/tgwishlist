# Start everything for local development with one command (Windows PowerShell 5.1+):
#   Docker Desktop -> PostgreSQL -> migrations -> backend -> frontend -> tunnel -> bot
# The new tunnel URL is written to backend/.env (WEBAPP_URL) before the bot starts.
#
# Usage:  powershell -ExecutionPolicy Bypass -File .\dev.ps1
# Stop:   powershell -ExecutionPolicy Bypass -File .\dev-stop.ps1
# Needs:  Docker Desktop, uv, Node.js, cloudflared (winget install Cloudflare.cloudflared)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$state = Join-Path $root '.dev'
$envFile = Join-Path $backend '.env'
$pidFile = Join-Path $state 'pids.txt'

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

# Native tools print to stderr; with 'Stop' that would abort the script, so relax it here.
function Test-Docker {
    $ErrorActionPreference = 'Continue'
    docker info *> $null
    return $LASTEXITCODE -eq 0
}

function Find-Tool($name, $fallback) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    if (Test-Path $fallback) { return $fallback }
    return $null
}

# A PID is "ours" only if that exact process (same start time) still runs.
function Get-OurProcesses {
    if (-not (Test-Path $pidFile)) { return @() }
    $alive = @()
    foreach ($line in Get-Content $pidFile) {
        $id, $ticks = $line -split ' '
        $p = Get-Process -Id $id -ErrorAction SilentlyContinue
        if ($p -and $p.StartTime.Ticks -eq [long]$ticks) { $alive += $p }
    }
    return $alive
}

New-Item -ItemType Directory -Force $state | Out-Null
if (@(Get-OurProcesses).Count -gt 0) {
    Write-Host 'dev.ps1 is already running. Run dev-stop.ps1 first.' -ForegroundColor Yellow
    exit 1
}
Remove-Item $pidFile -ErrorAction SilentlyContinue  # stale file, e.g. after a reboot

if (-not (Test-Path $envFile)) { throw 'backend/.env not found: copy .env.example and fill it in.' }
# The tunnel makes the app public: the "dev" login bypass must be off.
if (Select-String -Path $envFile -Pattern '^\s*DEV_AUTH\s*=\s*(true|1|yes|on)\s*$' -Quiet) {
    throw 'DEV_AUTH is on in backend/.env. Set DEV_AUTH=false: the tunnel would let anyone in.'
}
$cloudflared = Find-Tool 'cloudflared' 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
if (-not $cloudflared) { throw 'cloudflared not found (winget install Cloudflare.cloudflared).' }
$dockerDesktop = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'

function Quote($text) { return "'" + ($text -replace "'", "''") + "'" }

# Windows started by this script; dev-stop.ps1 closes exactly these.
function Start-Window($title, $dir, $command) {
    $full = "`$Host.UI.RawUI.WindowTitle = $(Quote $title); Set-Location $(Quote $dir); $command"
    $p = Start-Process powershell -ArgumentList '-NoProfile', '-NoExit', '-Command', $full -PassThru
    Add-Content -Path $pidFile -Value "$($p.Id) $($p.StartTime.Ticks)"
}

try {
    # --- Docker + PostgreSQL -----------------------------------------------------------
    Step 'Docker Desktop'
    if (-not (Test-Docker)) {
        if (-not (Test-Path $dockerDesktop)) { throw "Docker Desktop not found at $dockerDesktop" }
        Start-Process $dockerDesktop
        Write-Host 'Starting Docker Desktop (up to ~2 min)...'
        $ready = $false
        for ($i = 0; $i -lt 60 -and -not $ready; $i++) {
            Start-Sleep -Seconds 2
            $ready = Test-Docker
        }
        if (-not $ready) { throw 'Docker Desktop did not start.' }
    }

    Step 'PostgreSQL'
    Push-Location $root
    docker compose up -d --wait db
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { throw 'Database did not start.' }

    Step 'Backend dependencies and migrations'
    Push-Location $backend
    uv sync -q
    $code = $LASTEXITCODE
    if ($code -eq 0) { uv run alembic upgrade head; $code = $LASTEXITCODE }
    Pop-Location
    if ($code -ne 0) { throw 'uv sync or migrations failed.' }

    # --- Backend + frontend --------------------------------------------------------------
    Step 'Backend (http://localhost:8000)'
    Start-Window 'wishlist: backend' $backend 'uv run uvicorn app.main:app --reload'

    Step 'Frontend (http://localhost:5173)'
    Start-Window 'wishlist: frontend' $frontend 'npm run dev'

    # --- Tunnel: read its public URL from a fresh log --------------------------------------
    Step 'Tunnel (cloudflared)'
    $tunnelLog = Join-Path $state "tunnel-$(Get-Date -Format yyyyMMdd-HHmmss).log"
    Start-Window 'wishlist: tunnel' $root `
        "& $(Quote $cloudflared) tunnel --url http://localhost:5173 2>&1 | Tee-Object -FilePath $(Quote $tunnelLog)"

    # api.trycloudflare.com is cloudflared's own API, printed when the request fails.
    $pattern = 'https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com'
    $url = $null
    for ($i = 0; $i -lt 45 -and -not $url; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Path $tunnelLog) {
            $match = Select-String -Path $tunnelLog -Pattern $pattern | Select-Object -First 1
            if ($match) { $url = $match.Matches[0].Value }
        }
    }
    if (-not $url) { throw "Tunnel URL not found in $tunnelLog. Check the tunnel window." }
    Write-Host "Tunnel: $url" -ForegroundColor Green

    # --- Write WEBAPP_URL (UTF-8 without BOM, keep the rest of .env as is) --------------
    $found = $false
    $lines = @([System.IO.File]::ReadAllLines($envFile) | ForEach-Object {
            if ($_ -match '^WEBAPP_URL=') { $found = $true; "WEBAPP_URL=$url" } else { $_ }
        })
    if (-not $found) { $lines += "WEBAPP_URL=$url" }
    [System.IO.File]::WriteAllLines($envFile, [string[]]$lines, (New-Object System.Text.UTF8Encoding $false))
    Write-Host 'WEBAPP_URL updated in backend/.env'

    # --- Bot (after .env has the new URL) --------------------------------------------------
    Step 'Bot'
    Start-Window 'wishlist: bot' $backend 'uv run python -m app.bot.polling'
}
catch {
    Write-Host "`nFailed: $($_.Exception.Message)" -ForegroundColor Red
    if (Test-Path $pidFile) {
        Write-Host 'Closing the windows started so far...' -ForegroundColor Yellow
        & (Join-Path $root 'dev-stop.ps1')
    }
    exit 1
}

Write-Host "`nAll set. Send /start to the bot and open the app with the NEW button." -ForegroundColor Green
Write-Host "Mini App: $url"
Write-Host 'Stop everything: powershell -ExecutionPolicy Bypass -File .\dev-stop.ps1'
