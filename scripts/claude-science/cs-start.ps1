# cs-start — ensure Claude Science (WSL daemon) is up (gentle: never kills a running one) and open its UI.
$ErrorActionPreference = 'SilentlyContinue'
$status = wsl.exe -d Ubuntu -- bash -lc "claude-science status"
if ($status -notmatch '"running"\s*:\s*true') {
  Write-Host "Starting Claude Science daemon..."
  wsl.exe -d Ubuntu -- bash -lc "claude-science serve --no-browser --detached" | Out-Null
  Start-Sleep -Seconds 6
} else {
  Write-Host "Claude Science already running."
}
$o = wsl.exe -d Ubuntu -- bash -lc "claude-science url"
$line = $o | Where-Object { $_ -match 'http://localhost' } | Select-Object -First 1
if ($line) {
  $u = ([regex]'http://localhost:\d+/\S*').Match($line).Value
  if (-not $u) { $u = $line.Trim() }
  Start-Process $u
  Write-Host "UI opened: $u"
} else {
  Start-Process "http://localhost:8000"
}
