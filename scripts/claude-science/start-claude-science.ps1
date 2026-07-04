# Start Claude Science (WSL2 daemon) if not running, then open its UI in the Windows browser.
# Claude Science is a localhost web-UI daemon inside WSL2 Ubuntu; WSL2 forwards localhost:8000 to Windows.
$ErrorActionPreference = 'SilentlyContinue'

$status = wsl.exe -d Ubuntu -- bash -lc "claude-science status" 2>&1
if ($status -notmatch '"running"\s*:\s*true') {
  Write-Host "Starting Claude Science daemon..."
  wsl.exe -d Ubuntu -- bash -lc "claude-science serve --no-browser --detached" 2>&1 | Out-Null
  Start-Sleep -Seconds 6
} else {
  Write-Host "Claude Science daemon already running."
}

$out = wsl.exe -d Ubuntu -- bash -lc "claude-science url" 2>&1
$url = ($out | Where-Object { $_ -match 'http://localhost' } | Select-Object -First 1)
if ($url) { $url = $url.Trim() } else { $url = "http://localhost:8000" }
Write-Host "Opening: $url"
Start-Process $url
