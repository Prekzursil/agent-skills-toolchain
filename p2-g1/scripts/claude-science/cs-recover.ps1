# cs-recover -- recover/restart the Claude Science WSL daemon (clears the stale lock that
# makes a normal restart hang) and reopen the UI in the Windows browser.
#
# Config comes from cs-lib.ps1 (-> cs.conf -> env). Before 2026-08-12 this script hardcoded both
# the distro and the port, so it was one of five that silently ignored the seam cs-lib.ps1 had
# already established -- changing the port fixed cs.ps1 and left this one pointing at the old one.
$ErrorActionPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot 'cs-lib.ps1')
Write-Information -InformationAction Continue "Recovering Claude Science (killing stuck daemon, clearing stale locks, clean start)..."
wsl.exe -d $script:CSDistro -- bash -lc "cs-recover"
$o = wsl.exe -d $script:CSDistro -- bash -lc "claude-science url"
$line = $o | Where-Object { $_ -match 'https?://(localhost|127\.0\.0\.1)' } | Select-Object -First 1
if ($line) {
  $u = ([regex]'https?://(?:localhost|127\.0\.0\.1):\d+/\S*').Match($line).Value
  if (-not $u) { $u = $line.Trim() }
  Start-Process $u
  Write-Information -InformationAction Continue "Claude Science recovered - UI opened: $u"
} else {
  Start-Process $script:CSUrl
  Write-Information -InformationAction Continue "Recovered; opened $script:CSUrl"
}
