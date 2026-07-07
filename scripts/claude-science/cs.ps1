# cs — one-command dispatcher for the Claude Science WSL2 daemon (local).
#   cs open    ensure up (wait for readiness, not a blind sleep) then open the UI
#   cs ensure  headless ensure-up for other tools/agents -> SUCCESS:cs-up / FAILED:cs-down
#   cs status  [-Json]  human or machine-readable state incl. measured latency + wedged flag
#   cs fix     force-recover (graceful stop -> clear locks -> restart)  [alias: recover]
#   cs stop    stop the daemon    |   cs backup    |   cs restore <ts|latest>
#   cs doctor  full-stack PASS/WARN/FAIL report    |   cs help
[CmdletBinding()]
param(
  [Parameter(Position = 0)][string]$Verb = 'help',
  [Parameter(Position = 1)][string]$Arg,
  [switch]$Json
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'cs-lib.ps1')   # Invoke-CSWsl, Test-CSHealth, Wait-CSAlive, $script:CSUrl

function Invoke-EnsureUp {
  # start-if-down / recover-if-wedged / no-op-if-healthy, then block until ready.
  $h = Test-CSHealth
  switch ($h.State) {
    'HEALTHY' { return $true }
    'SLOW'    { Write-Host "wedged ($($h.Ms)ms) -> recover"; [void](Invoke-CSWsl 'cs-recover' 75) }
    'DOWN'    { Write-Host 'down -> start';                  [void](Invoke-CSWsl 'cs-start' 45) }
  }
  return (Wait-CSAlive)
}

switch ($Verb.ToLower()) {
  'ensure' { if (Invoke-EnsureUp) { Write-Output 'SUCCESS:cs-up'; exit 0 } else { Write-Output 'FAILED:cs-down'; exit 1 } }
  'open'   { if (Invoke-EnsureUp) { Start-Process $script:CSUrl; Write-Host "opened $script:CSUrl" } else { Write-Warning 'CS did not come up; run: cs doctor'; exit 1 } }
  { $_ -in 'fix', 'recover' } { Write-Host (Invoke-CSWsl 'cs-recover' 75) }
  'stop'    { Write-Host (Invoke-CSWsl 'claude-science stop' 20) }
  'backup'  { Write-Host (Invoke-CSWsl 'cs-backup' 90) }
  'restore' { if (-not $Arg) { Write-Warning 'usage: cs restore <timestamp|latest>'; exit 1 }; Write-Host (Invoke-CSWsl "cs-restore $Arg" 120) }
  'status'  {
    $h = Test-CSHealth
    $wsl = (Invoke-CSWsl 'claude-science status 2>/dev/null || echo {}' 15)
    $wedged = ($h.State -eq 'SLOW')
    if ($Json) {
      ([ordered]@{ state = $h.State; http = $h.Http; latency_ms = $h.Ms; wedged = $wedged; url = $script:CSUrl; wsl_status = $wsl }) | ConvertTo-Json -Compress
    } else {
      "state    : {0} (http {1}, {2}ms){3}" -f $h.State, $h.Http, $h.Ms, $(if ($wedged) { ' *** WEDGED ***' } else { '' })
      "url      : $script:CSUrl"
      "daemon   : $wsl"
    }
  }
  'doctor'  { & (Join-Path $PSScriptRoot 'cs-doctor.ps1') }
  default   {
    @'
cs — Claude Science (local) control
  cs open              ensure up (wait for readiness) + open the UI
  cs ensure            headless ensure-up  -> SUCCESS:cs-up / FAILED:cs-down (for tools/agents)
  cs status [-Json]    state incl. latency + wedged flag
  cs fix               force-recover (graceful)      cs stop    stop the daemon
  cs backup            online SQLite backup          cs restore <ts|latest>
  cs doctor            full-stack PASS/WARN/FAIL report
401 on / = alive (auth gate). A slow/timeout response = WEDGED (WSL frozen, usually host-RAM).
'@
  }
}
