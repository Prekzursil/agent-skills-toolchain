# bm-watchdog - keeps the local Biomini gradio daemon available (the cs-watchdog pattern).
# Runs via Scheduled Task 'BiominiStackGuard'. Heartbeat + recover-log so bm-doctor
# can verify it independently (beat freshness OR live process - two signals).
[CmdletBinding()]
param(
  [int]$IntervalSec = 60,
  [int]$MaxLoops = 0   # 0 = until stopped (Task Scheduler owns lifetime)
)
$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'bm-lib.ps1')

$beat = Join-Path $env:LOCALAPPDATA 'biomni-watchdog.heartbeat'
$recLog = Join-Path $env:LOCALAPPDATA 'biomni-watchdog.log'

$i = 0
while ($MaxLoops -eq 0 -or $i -lt $MaxLoops) {
  $i++
  try { Set-Content -Path $beat -Value (Get-Date -Format o) -ErrorAction SilentlyContinue } catch {}

  $h = Test-BMHealth
  if ($h.State -ne 'HEALTHY') {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $recLog -Value "$stamp recover ($($h.State) http=$($h.Http) ms=$($h.Ms))"
    [void](Invoke-BMWsl 'bm-recover' 75)
    if (Wait-BMAlive 150) {
      Add-Content -Path $recLog -Value "$stamp recovered"
    } else {
      Add-Content -Path $recLog -Value "$stamp recover FAILED (daemon never reached HEALTHY)"
    }
  }
  Start-Sleep -Seconds $IntervalSec
}
