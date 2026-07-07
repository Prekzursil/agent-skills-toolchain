# cs - one-command dispatcher for the Claude Science WSL2 daemon (local).
#   cs open    ensure up (wait for readiness, not a blind sleep) then open the UI + apply the tab-death regfix
#   cs ensure  headless ensure-up for other tools/agents -> SUCCESS:cs-up / FAILED:cs-down
#   cs status  [-Json]  human or machine-readable state incl. measured latency + wedged flag
#   cs fix     force-recover (graceful stop -> clear locks -> restart)  [alias: recover]
#   cs stop    stop the daemon    |   cs backup    |   cs restore <ts|latest>
#   cs doctor  full-stack PASS/WARN/FAIL report    |   cs help
# ASCII-only on purpose (no BOM needed; cs.cmd invokes this under Windows PowerShell 5.1).
[CmdletBinding()]
param(
  [Parameter(Position = 0)][string]$Verb = 'help',
  [Parameter(Position = 1)][string]$Arg,
  [switch]$Json
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'cs-lib.ps1')   # Invoke-CSWsl, Test-CSHealth, Wait-CSAlive, $script:CSUrl

function Write-CSInfo {
  # Progress/diagnostics -> the information stream (6), NOT stdout: keeps `cs ensure` output a clean
  # terminal-state marker while staying visible on the console for `cs open`. PSScriptAnalyzer-safe
  # (no Write-Host). -InformationAction Continue makes it visible regardless of $InformationPreference.
  param([string]$Message)
  Write-Information -MessageData $Message -InformationAction Continue
}

function Set-CSTabRegfix {
  # Idempotent HKCU policy so Chrome/Edge never sleep/discard the Claude Science tab (a discarded
  # tab drops the WebSocket -> the UI reads as 'dead'). Applied on `cs open` AND by install.ps1;
  # a no-op when already set. State-changing verb -> SupportsShouldProcess (analyzer-clean).
  [CmdletBinding(SupportsShouldProcess)]
  param()
  $urls = @('claude.ai', '[*.]claude.ai', 'localhost', '127.0.0.1')
  $keys = @(
    'HKCU:\SOFTWARE\Policies\Google\Chrome\TabDiscardingExceptions',
    'HKCU:\SOFTWARE\Policies\Microsoft\Edge\SleepingTabsBlockedForUrls'
  )
  foreach ($key in $keys) {
    if (-not $PSCmdlet.ShouldProcess($key, 'apply Claude Science tab-death exceptions')) { continue }
    try {
      if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
      for ($i = 0; $i -lt $urls.Count; $i++) {
        New-ItemProperty -Path $key -Name ([string]($i + 1)) -Value $urls[$i] -PropertyType String -Force | Out-Null
      }
    } catch {
      Write-CSInfo "tab-death regfix skipped for $key ($($_.Exception.Message))"
    }
  }
}

function Invoke-EnsureUp {
  # start-if-down / recover-if-wedged / no-op-if-healthy, then block until ready (poll, not sleep).
  $h = Test-CSHealth
  switch ($h.State) {
    'HEALTHY' { return $true }
    'SLOW'    { Write-CSInfo "wedged ($($h.Ms)ms) -> recover"; [void](Invoke-CSWsl 'cs-recover' 75) }
    'DOWN'    { Write-CSInfo 'down -> start'; [void](Invoke-CSWsl 'cs-start' 45) }
  }
  return (Wait-CSAlive 30)
}

function Get-CSStatus {
  # Full machine-readable state for other tools/agents. ONE combined WSL round-trip (wsl_up + free
  # disk + daemon json) plus cheap local host/watchdog reads, so `cs status` stays responsive.
  $h = Test-CSHealth
  $blob = Invoke-CSWsl 'echo __WSLUP__; df -BG --output=avail "$HOME" 2>/dev/null | tail -1 | tr -dc 0-9; echo; claude-science status 2>/dev/null || true' 15
  $wslUp = (($blob -ne '__WSL_TIMEOUT__') -and ($blob -match '__WSLUP__'))

  $diskGb = $null
  $dm = [regex]::Match($blob, '__WSLUP__\s*\r?\n\s*(\d+)')
  if ($dm.Success) { $diskGb = [int]$dm.Groups[1].Value }

  $dpid = $null
  $pm = [regex]::Match($blob, '"pid":\s*(\d+)')
  if ($pm.Success) { $dpid = [int]$pm.Groups[1].Value }

  $port = 8000
  $portm = [regex]::Match($blob, '"port":\s*(\d+)')
  if ($portm.Success) { $port = [int]$portm.Groups[1].Value }

  $ramGb = $null
  try {
    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    $ramGb = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
  } catch {
    $ramGb = $null
  }

  $beat = Join-Path $env:LOCALAPPDATA 'claude-science-watchdog.heartbeat'
  $wdAlive = $false
  if (Test-Path $beat) { $wdAlive = (((Get-Date) - (Get-Item $beat).LastWriteTime).TotalSeconds -lt 90) }

  $lastRecover = $null
  $log = Join-Path $env:LOCALAPPDATA 'claude-science-watchdog.log'
  if (Test-Path $log) {
    $line = Select-String -Path $log -Pattern ' recover \(' -ErrorAction SilentlyContinue | Select-Object -Last 1
    if ($line) {
      $rm = [regex]::Match($line.Line, '^(\S+)')
      if ($rm.Success) { $lastRecover = $rm.Groups[1].Value }
    }
  }

  return [ordered]@{
    running          = ($h.State -ne 'DOWN')
    wedged           = ($h.State -eq 'SLOW')
    http_status      = $h.Http
    latency_ms       = $h.Ms
    pid              = $dpid
    port             = $port
    url              = $script:CSUrl
    wsl_up           = $wslUp
    free_wsl_disk_gb = $diskGb
    host_free_ram_gb = $ramGb
    watchdog_alive   = $wdAlive
    last_recover     = $lastRecover
  }
}

switch ($Verb.ToLower()) {
  'ensure' { if (Invoke-EnsureUp) { Write-Output 'SUCCESS:cs-up'; exit 0 } else { Write-Output 'FAILED:cs-down'; exit 1 } }
  'open' {
    if (Invoke-EnsureUp) {
      Set-CSTabRegfix
      Start-Process $script:CSUrl
      Write-CSInfo "opened $script:CSUrl"
    } else {
      Write-Warning 'CS did not come up; run: cs doctor'
      exit 1
    }
  }
  { $_ -in 'fix', 'recover' } { Write-Output (Invoke-CSWsl 'cs-recover' 75) }
  'stop' { Write-Output (Invoke-CSWsl 'claude-science stop' 20) }
  'backup' { Write-Output (Invoke-CSWsl 'cs-backup' 90) }
  'restore' {
    if (-not $Arg) { Write-Warning 'usage: cs restore <timestamp|latest>'; exit 1 }
    Write-Output (Invoke-CSWsl "cs-restore $Arg" 120)
  }
  'status' {
    $s = Get-CSStatus
    if ($Json) {
      $s | ConvertTo-Json -Compress
    } else {
      $state = if ($s.running) { if ($s.wedged) { 'SLOW' } else { 'HEALTHY' } } else { 'DOWN' }
      $wedgeTag = if ($s.wedged) { ' *** WEDGED ***' } else { '' }
      "state    : {0} (http {1}, {2}ms){3}" -f $state, $s.http_status, $s.latency_ms, $wedgeTag
      "url      : {0}  (pid {1}, port {2})" -f $s.url, $s.pid, $s.port
      "wsl      : up={0}  disk_free={1}GB  host_ram_free={2}GB" -f $s.wsl_up, $s.free_wsl_disk_gb, $s.host_free_ram_gb
      "watchdog : alive={0}  last_recover={1}" -f $s.watchdog_alive, $(if ($s.last_recover) { $s.last_recover } else { 'n/a' })
    }
  }
  'doctor' { & (Join-Path $PSScriptRoot 'cs-doctor.ps1') }
  default {
    @'
cs - Claude Science (local) control
  cs open              ensure up (wait for readiness) + open the UI + apply tab-death regfix
  cs ensure            headless ensure-up  -> SUCCESS:cs-up / FAILED:cs-down (for tools/agents)
  cs status [-Json]    state incl. latency + wedged flag (12-field JSON for other tools)
  cs fix               force-recover (graceful)      cs stop    stop the daemon
  cs backup            online SQLite backup          cs restore <ts|latest>
  cs doctor            full-stack PASS/WARN/FAIL report
401 on / = alive (auth gate). A slow/timeout response = WEDGED (WSL frozen, usually host-RAM).
'@
  }
}
