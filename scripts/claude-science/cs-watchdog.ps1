# cs-watchdog — Windows-side supervisor for the Claude Science WSL2 daemon.
# The single most robust layer (no sudo): it lives OUTSIDE WSL, so it recovers states
# nothing inside WSL can (idle-terminated distro, hung daemon, post-reboot). It:
#   - keepalives WSL every cycle ('wsl -e true' < the ~60s idle timeout) so the distro never sleeps
#   - probes 127.0.0.1:8000 (any HTTP status incl. 401 = alive; no response = DOWN/WEDGED)
#   - auto-recovers with a 2-strike debounce + a crash-loop breaker (max 3 recoveries / 15 min)
#   - disk-guards: warns when the WSL ext4 drops below the floor (disk-full mid-WAL = corruption)
# Written to run under BOTH Windows PowerShell 5.1 (Task Scheduler default) and pwsh 7.
# Registered at logon by register-tasks.ps1. Logs to %LOCALAPPDATA%\claude-science-watchdog.log
$ErrorActionPreference = 'SilentlyContinue'
$Distro    = 'Ubuntu'
$Url       = 'http://127.0.0.1:8000/'
$MinFreeGB = 10
$Log       = Join-Path $env:LOCALAPPDATA 'claude-science-watchdog.log'
$fails = 0
$recoveries = 0
$lastRecover = [DateTime]::MinValue

function Write-WdLog($m) {
  ("{0}  {1}" -f (Get-Date).ToString('s'), $m) | Out-File -Append -Encoding utf8 -FilePath $Log
}

function Test-DaemonAlive {
  # any HTTP response (incl. 401 auth gate) = alive; no response = down/wedged. 5.1- and 7-safe.
  try {
    $req = [System.Net.HttpWebRequest]::Create($Url)
    $req.Timeout = 5000
    $req.Method = 'GET'
    $resp = $req.GetResponse()
    $resp.Close()
    return $true
  } catch [System.Net.WebException] {
    if ($_.Exception.Response) { return $true }
    return $false
  } catch {
    return $false
  }
}

Write-WdLog "watchdog started (probe=$Url interval=30s floor=${MinFreeGB}GB)"
$tick = 0
while ($true) {
  & wsl -d $Distro -e true 2>$null            # keepalive: hold a WSL process < idle timeout

  if (Test-DaemonAlive) {
    $fails = 0
    if (((Get-Date) - $lastRecover).TotalMinutes -ge 15) { $recoveries = 0 }
  } else {
    $fails++
    if ($fails -ge 2) {                         # 2-strike debounce (ignore a transient GC pause)
      if ($recoveries -ge 3 -and ((Get-Date) - $lastRecover).TotalMinutes -lt 15) {
        Write-WdLog "CRASH-LOOP BREAKER tripped ($recoveries recoveries/15min) - backing off, NOT restarting. Investigate."
      } else {
        Write-WdLog "unhealthy x$fails -> cs-recover"
        & wsl -d $Distro -e sh -lc 'cs-recover' 2>$null
        $recoveries++
        $lastRecover = Get-Date
        $fails = 0
      }
    }
  }

  $tick++
  if ($tick % 10 -eq 0) {                        # disk guard ~every 5 min
    $free = & wsl -d $Distro -e sh -lc 'df -BG --output=avail "$HOME" | tail -1 | tr -dc 0-9' 2>$null
    $g = 0
    if ($free -and [int]::TryParse(("$free").Trim(), [ref]$g) -and $g -lt $MinFreeGB) {
      Write-WdLog "LOW DISK: ${g}GB free on WSL ext4 (< ${MinFreeGB}GB) - disk-full mid-WAL risks DB corruption."
    }
  }

  Start-Sleep -Seconds 30
}
