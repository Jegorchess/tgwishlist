# Stop everything started by dev.ps1 (only those windows and their child processes).
# The database container keeps running (it's cheap); stop it with: docker compose stop db
#
# Usage:  powershell -ExecutionPolicy Bypass -File .\dev-stop.ps1

$pidFile = Join-Path $PSScriptRoot '.dev\pids.txt'
if (-not (Test-Path $pidFile)) {
    Write-Host 'Nothing to stop.'
    exit 0
}

$stopped = 0
foreach ($line in Get-Content $pidFile) {
    $id, $ticks = $line -split ' '
    $p = Get-Process -Id $id -ErrorAction SilentlyContinue
    # Only the exact process dev.ps1 started: after a reboot the PID may belong to
    # something else entirely.
    if ($p -and $ticks -and $p.StartTime.Ticks -eq [long]$ticks) {
        # /T also stops children: uvicorn, node, cloudflared, the bot.
        taskkill /PID $id /T /F *> $null
        $stopped++
    }
}
Remove-Item $pidFile
Write-Host "Stopped $stopped window(s): backend, frontend, tunnel, bot."
