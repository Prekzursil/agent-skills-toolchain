# cs-lib -- shared Claude Science health/probe helpers.
# Dot-sourced by cs.ps1, cs-doctor.ps1, and cs-watchdog.ps1 so the wedge-detection is identical
# everywhere (no drift). A wedged daemon (WSL frozen under host-RAM pressure) still ACCEPTS the
# socket but answers slowly/never -> latency is the signal the old any-HTTP-status probe missed.
$script:CSDistro  = 'Ubuntu'
$script:CSUrl     = 'http://127.0.0.1:8000/'
$script:CSSlowMs  = 4000     # >= this response time = SLOW (wedge candidate); healthy 401 < 200ms
$script:CSHardCap = 8000     # ms socket/read timeout; an accepted-but-frozen socket hits this

function Invoke-CSWsl {
  # Run a WSL login-shell command with a HARD timeout, so a frozen VM can never hang the caller.
  # Job inputs are passed explicitly via -ArgumentList and received through param($d,$c) below --
  # no closure capture, so $using: does not apply (PSSA false positive). Live-verified: cs status
  # gathers WSL pid/disk/RAM through this path correctly.
  [Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSUseUsingScopeModifierInNewRunspaces', '', Justification = 'Args passed via -ArgumentList/param(), not closure-captured.')]
  param([string]$Cmd, [int]$TimeoutSec = 20)
  $job = Start-Job { param($d, $c) & wsl.exe -d $d -e bash -lc "export PATH=`$HOME/.local/bin:`$PATH; $c" 2>&1 } -ArgumentList $script:CSDistro, $Cmd
  if (Wait-Job $job -Timeout $TimeoutSec) { $o = Receive-Job $job; Remove-Job $job -Force -ErrorAction SilentlyContinue; return ($o -join "`n") }
  Stop-Job $job -ErrorAction SilentlyContinue; Remove-Job $job -Force -ErrorAction SilentlyContinue
  return '__WSL_TIMEOUT__'
}

function Test-CSHealth {
  # -> @{ State = HEALTHY|SLOW|DOWN ; Ms = <int> ; Http = <code|null> }
  param([int]$SlowMs = $script:CSSlowMs, [int]$HardCapMs = $script:CSHardCap, [string]$Url = $script:CSUrl)
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  try {
    $req = [System.Net.HttpWebRequest]::Create($Url)
    $req.Timeout = $HardCapMs; $req.ReadWriteTimeout = $HardCapMs; $req.Method = 'GET'; $req.KeepAlive = $false
    $resp = $req.GetResponse(); $sw.Stop(); $code = [int]$resp.StatusCode; $resp.Close()
    return @{ State = $(if ($sw.ElapsedMilliseconds -ge $SlowMs) { 'SLOW' } else { 'HEALTHY' }); Ms = [int]$sw.ElapsedMilliseconds; Http = $code }
  } catch [System.Net.WebException] {
    $sw.Stop(); $we = $_.Exception
    if ($we.Response) { return @{ State = $(if ($sw.ElapsedMilliseconds -ge $SlowMs) { 'SLOW' } else { 'HEALTHY' }); Ms = [int]$sw.ElapsedMilliseconds; Http = [int]$we.Response.StatusCode } }
    if ($we.Status -eq [System.Net.WebExceptionStatus]::Timeout) { return @{ State = 'SLOW'; Ms = [int]$sw.ElapsedMilliseconds; Http = $null } }
    return @{ State = 'DOWN'; Ms = -1; Http = $null }
  } catch { $sw.Stop(); return @{ State = 'DOWN'; Ms = -1; Http = $null } }
}

function Wait-CSAlive {
  param([int]$TimeoutSec = 45)
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  do { if ((Test-CSHealth).State -eq 'HEALTHY') { return $true }; Start-Sleep -Milliseconds 1000 } while ((Get-Date) -lt $deadline)
  return $false
}
