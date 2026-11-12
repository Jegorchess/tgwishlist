# Stop everything started by dev.ps1 (only those windows and their child processes).
# The database container keeps running (it's cheap); stop it with: docker compose stop db
#
# Usage:  powershell -ExecutionPolicy Bypass -File .\dev-stop.ps1

$pidFile = Join-Path $PSScriptRoot '.dev\pids.txt'
if (-not (Test-Path $pidFile)) {
    Write-Host 'Nothing to stop (no .dev\pids.txt).'
    exit 0
}

foreach ($id in Get-Content $pidFile) {
    if ($id -match '^\d+$') {
        # /T also stops children: uvicorn, node, cloudflared, the bot.
        taskkill /PID $id /T /F *> $null
    }
}
Remove-Item $pidFile
Write-Host 'Stopped backend, frontend, tunnel and bot.'
