# cs-recover -- recover/restart the Claude Science WSL daemon (clears the stale lock that
# makes a normal restart hang) and reopen the UI in the Windows browser.
$ErrorActionPreference = 'SilentlyContinue'
Write-Information -InformationAction Continue "Recovering Claude Science (killing stuck daemon, clearing stale locks, clean start)..."
wsl.exe -d Ubuntu -- bash -lc "cs-recover"
$o = wsl.exe -d Ubuntu -- bash -lc "claude-science url"
$line = $o | Where-Object { $_ -match 'http://localhost' } | Select-Object -First 1
if ($line) {
  $u = ([regex]'http://localhost:\d+/\S*').Match($line).Value
  if (-not $u) { $u = $line.Trim() }
  Start-Process $u
  Write-Information -InformationAction Continue "Claude Science recovered - UI opened: $u"
} else {
  Start-Process "http://localhost:8000"
  Write-Information -InformationAction Continue "Recovered; opened http://localhost:8000"
}
