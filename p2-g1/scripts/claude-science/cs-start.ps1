# cs-start -- ensure Claude Science (WSL daemon) is up (gentle: never kills a running one) and open its UI.
#
# Config comes from cs-lib.ps1 (-> cs.conf -> env); see the note in cs-recover.ps1 about the five
# scripts that used to bypass the seam.
$ErrorActionPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot 'cs-lib.ps1')
$status = wsl.exe -d $script:CSDistro -- bash -lc "claude-science status"
if ($status -notmatch '"running"\s*:\s*true') {
  Write-Information -InformationAction Continue "Starting Claude Science daemon..."
  wsl.exe -d $script:CSDistro -- bash -lc "claude-science serve --no-browser --detached" | Out-Null
  Start-Sleep -Seconds 6
} else {
  Write-Information -InformationAction Continue "Claude Science already running."
}
$o = wsl.exe -d $script:CSDistro -- bash -lc "claude-science url"
$line = $o | Where-Object { $_ -match 'https?://(localhost|127\.0\.0\.1)' } | Select-Object -First 1
if ($line) {
  $u = ([regex]'https?://(?:localhost|127\.0\.0\.1):\d+/\S*').Match($line).Value
  if (-not $u) { $u = $line.Trim() }
  Start-Process $u
  Write-Information -InformationAction Continue "UI opened: $u"
} else {
  Start-Process $script:CSUrl
}
