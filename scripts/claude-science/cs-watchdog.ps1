# cs-watchdog — Windows-side supervisor for the Claude Science WSL2 daemon (the OUTER net:
# recovers idled-out distro / hung daemon / post-reboot states nothing inside WSL can).
# Hardened 2026-07-07 (audit): single-instance MUTEX (was: two instances racing cs-recover and
# killing each other's daemon), LATENCY-aware wedge detection (was: any-HTTP=alive, blind to the
# ~164s freeze), HEARTBEAT file (hung != healthy), TIMEOUT-wrapped wsl calls (a frozen VM used to
# hang the loop -> keepalive stopped -> 60s idle-kill -> silent death), immediate ensure-up on
# start (no 60s 2-strike gap), host-RAM WARN guard (the oversubscription that causes the freeze),
# log rotation, and post-recover re-probe (was: reset $fails regardless of outcome).
$ErrorActionPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot 'cs-lib.ps1')     # Test-CSHealth, Invoke-CSWsl, $script:CSUrl/CSDistro/CSSlowMs
$Log         = Join-Path $env:LOCALAPPDATA 'claude-science-watchdog.log'
$Beat        = Join-Path $env:LOCALAPPDATA 'claude-science-watchdog.heartbeat'
$MinFreeGB   = 10       # WSL ext4 floor (disk-full mid-WAL risks DB corruption)
$MinRamGB    = 3        # host free-RAM floor (below = warn; oversubscription freezes WSL = the wedge)
$SlowStrikes = 3        # consecutive SLOW probes (~90s) => wedged => recover
$DownStrikes = 2        # consecutive DOWN probes => recover

function Write-WdLog($m) { ("{0}  {1}" -f (Get-Date).ToString('s'), $m) | Out-File -Append -Encoding utf8 -FilePath $Log }
function Write-Beat($state, $ms) { "$([DateTime]::UtcNow.ToString('o')) state=$state latency=${ms}ms recoveries=$script:recoveries" | Set-Content -Encoding utf8 -Path $Beat }

# --- single-instance guard: first writer wins, late starters exit (kills the dual-watchdog race) ---
$mtx = New-Object System.Threading.Mutex($false, 'Global\ClaudeScienceWatchdog')
$own = $false
try { $own = $mtx.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $own = $true }   # prior instance died holding it
if (-not $own) { Write-WdLog 'another watchdog already holds the mutex - exiting'; exit 0 }

# --- log rotation (was: unbounded Out-File -Append) ---
if ((Test-Path $Log) -and (Get-Item $Log).Length -gt 5MB) { Move-Item $Log "$Log.1" -Force }

$fails = 0; $slow = 0; $script:recoveries = 0; $script:lastRecover = [DateTime]::MinValue; $tick = 0
Write-WdLog "watchdog started (probe=$script:CSUrl slow>=$($script:CSSlowMs)ms strikes=$SlowStrikes; disk floor=${MinFreeGB}GB ram floor=${MinRamGB}GB)"

# --- immediate ensure-up: do the obvious first start now, don't wait for 2 failed strikes ---
Write-WdLog 'startup: ensuring CS is up'
[void](Invoke-CSWsl 'cs-start' 45)

function Invoke-WdRecover($why) {
  if ($script:recoveries -ge 3 -and ((Get-Date) - $script:lastRecover).TotalMinutes -lt 15) {
    Write-WdLog "CRASH-LOOP BREAKER tripped ($script:recoveries recoveries/15min) - backing off, NOT restarting. Investigate: cs doctor"
    return
  }
  Write-WdLog "recover ($why)"
  $r = Invoke-CSWsl 'cs-recover' 75
  if ($r -eq '__WSL_TIMEOUT__') { Write-WdLog 'cs-recover WSL call TIMED OUT (VM wedged) - terminating distro for a clean boot'; & wsl.exe -t $script:CSDistro 2>$null }
  $script:recoveries++; $script:lastRecover = Get-Date
}

while ($true) {
  $h = Test-CSHealth
  Write-Beat $h.State $h.Ms
  switch ($h.State) {
    'HEALTHY' { $fails = 0; $slow = 0; if (((Get-Date) - $script:lastRecover).TotalMinutes -ge 15) { $script:recoveries = 0 } }
    'SLOW'    { $slow++; $fails = 0; if ($slow -ge $SlowStrikes) { Invoke-WdRecover "WEDGE latency=$($h.Ms)ms"; $slow = 0; Start-Sleep 8; if ((Test-CSHealth).State -ne 'HEALTHY') { Write-WdLog 'still unhealthy after wedge-recover' } } }
    'DOWN'    { $slow = 0; $fails++; if ($fails -ge $DownStrikes) { Invoke-WdRecover 'DOWN'; Start-Sleep 8; if ((Test-CSHealth).State -eq 'DOWN') { Write-WdLog 'still DOWN after recover' } else { $fails = 0 } } }
  }

  $tick++
  if ($tick % 10 -eq 0) {
    $os = Get-CimInstance Win32_OperatingSystem
    $ramGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
    if ($ramGB -lt $MinRamGB) {
      $t = Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 1
      Write-WdLog ("LOW HOST RAM: ${ramGB}GB free (< ${MinRamGB}GB) - WSL freeze/wedge risk. top: {0} {1}MB" -f $t.ProcessName, [math]::Round($t.WorkingSet64 / 1MB))
    }
    $free = Invoke-CSWsl 'df -BG --output=avail "$HOME" | tail -1 | tr -dc 0-9' 15
    $g = 0
    if ($free -ne '__WSL_TIMEOUT__' -and [int]::TryParse(("$free").Trim(), [ref]$g) -and $g -lt $MinFreeGB) {
      Write-WdLog "LOW WSL DISK: ${g}GB free (< ${MinFreeGB}GB) - disk-full mid-WAL risks DB corruption."
    }
  }
  Start-Sleep -Seconds 30
}
