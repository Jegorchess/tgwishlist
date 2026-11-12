# Start everything for local development with one command (Windows PowerShell 5.1+):
#   Docker Desktop -> PostgreSQL -> migrations -> backend -> frontend -> tunnel -> bot
# The new tunnel URL is written to backend/.env (WEBAPP_URL) before the bot starts.
#
# Usage:  powershell -ExecutionPolicy Bypass -File .\dev.ps1
# Stop:   powershell -ExecutionPolicy Bypass -File .\dev-stop.ps1

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$state = Join-Path $root '.dev'
$envFile = Join-Path $backend '.env'
$cloudflared = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

New-Item -ItemType Directory -Force $state | Out-Null
$pidFile = Join-Path $state 'pids.txt'
if (Test-Path $pidFile) {
    Write-Host "Looks like dev.ps1 is already running (found $pidFile)." -ForegroundColor Yellow
    Write-Host 'Run dev-stop.ps1 first.' -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path $envFile)) { throw "backend/.env not found: copy .env.example and fill it in." }
if (-not (Test-Path $cloudflared)) { throw "cloudflared not found at $cloudflared (winget install Cloudflare.cloudflared)" }

# Windows started by this script; dev-stop.ps1 closes exactly these.
$started = @()
function Start-Window($title, $dir, $command) {
    $full = "`$Host.UI.RawUI.WindowTitle = '$title'; Set-Location '$dir'; $command"
    $p = Start-Process powershell -ArgumentList '-NoExit', '-Command', $full -PassThru
    $script:started += $p.Id
    Set-Content -Path $pidFile -Value $script:started
}

# --- Docker + PostgreSQL ---------------------------------------------------------------
Step 'Docker Desktop'
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
    Write-Host 'Starting Docker Desktop (up to ~2 min)...'
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 2
        docker info *> $null
        if ($LASTEXITCODE -eq 0) { break }
    }
    if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop did not start.' }
}

Step 'PostgreSQL'
Push-Location $root
docker compose up -d --wait db
if ($LASTEXITCODE -ne 0) { Pop-Location; throw 'Database did not start.' }
Pop-Location

Step 'Backend dependencies and migrations'
Push-Location $backend
uv sync -q
uv run alembic upgrade head
if ($LASTEXITCODE -ne 0) { Pop-Location; throw 'Migrations failed.' }
Pop-Location

# --- Backend + frontend -------------------------------------------------------------------
Step 'Backend (http://localhost:8000)'
Start-Window 'wishlist: backend' $backend 'uv run uvicorn app.main:app --reload'

Step 'Frontend (http://localhost:5173)'
Start-Window 'wishlist: frontend' $frontend 'npm run dev'

# --- Tunnel: read its public URL from the log ---------------------------------------------
Step 'Tunnel (cloudflared)'
$tunnelLog = Join-Path $state 'tunnel.log'
Remove-Item $tunnelLog -ErrorAction SilentlyContinue
Start-Window 'wishlist: tunnel' $root "& '$cloudflared' tunnel --url http://localhost:5173 2>&1 | Tee-Object -FilePath '$tunnelLog'"

$url = $null
for ($i = 0; $i -lt 45 -and -not $url; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $tunnelLog) {
        $match = Select-String -Path $tunnelLog -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' |
            Select-Object -First 1
        if ($match) { $url = $match.Matches[0].Value }
    }
}
if (-not $url) { throw "Tunnel URL not found in $tunnelLog. Check the tunnel window." }
Write-Host "Tunnel: $url" -ForegroundColor Green

# --- Write WEBAPP_URL (UTF-8 without BOM, keep the rest of .env as is) -------------------
$lines = [System.IO.File]::ReadAllLines($envFile)
$found = $false
$lines = $lines | ForEach-Object {
    if ($_ -match '^WEBAPP_URL=') { $found = $true; "WEBAPP_URL=$url" } else { $_ }
}
if (-not $found) { $lines += "WEBAPP_URL=$url" }
[System.IO.File]::WriteAllLines($envFile, [string[]]$lines, (New-Object System.Text.UTF8Encoding $false))
Write-Host 'WEBAPP_URL updated in backend/.env'

# --- Bot (after .env has the new URL) -----------------------------------------------------
Step 'Bot'
Start-Window 'wishlist: bot' $backend 'uv run python -m app.bot.polling'

Write-Host "`nAll set. Send /start to the bot and open the app with the NEW button." -ForegroundColor Green
Write-Host "Mini App: $url"
Write-Host 'Stop everything: powershell -ExecutionPolicy Bypass -File .\dev-stop.ps1'
