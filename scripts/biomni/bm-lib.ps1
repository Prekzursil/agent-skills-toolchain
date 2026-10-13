# bm-lib -- shared Biomni config + health/probe helpers (the cs-lib pattern).
# Dot-sourced by bm.ps1, bm-doctor.ps1, bm-watchdog.ps1 so wedge detection and
# config are identical everywhere. A wedged WSL still accepts the socket but
# answers slowly/never -> latency is the signal an any-HTTP probe misses.

# --- config: bm.conf (SSOT) -> defaults, env overrides both -----------------------------
$script:BMConfPath = Join-Path $PSScriptRoot 'bm.conf'
$script:BMConf = @{}
if (Test-Path $script:BMConfPath) {
  foreach ($line in (Get-Content -LiteralPath $script:BMConfPath -ErrorAction SilentlyContinue)) {
    $t = $line.Trim()
    if (-not $t -or $t.StartsWith('#')) { continue }
    $i = $t.IndexOf('=')
    if ($i -lt 1) { continue }
    $script:BMConf[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim()
  }
}
function Get-BMSetting {
  param([string]$Key, [string]$Default)
  $envVal = [Environment]::GetEnvironmentVariable($Key)
  if ($envVal) { return $envVal }
  if ($script:BMConf.ContainsKey($Key) -and $script:BMConf[$Key]) { return $script:BMConf[$Key] }
  return $Default
}
function Get-BMSettingInt {
  param([string]$Key, [int]$Default)
  $v = 0
  if ([int]::TryParse((Get-BMSetting $Key "$Default"), [ref]$v)) { return $v }
  return $Default
}

$script:BMHost     = Get-BMSetting    'BM_HOST'     '127.0.0.1'
$script:BMPort     = Get-BMSettingInt 'BM_PORT'     7860
$script:BMDistro   = Get-BMSetting    'BM_DISTRO'   'Ubuntu'
$script:BMSlowMs   = Get-BMSettingInt 'BM_SLOW_MS'  4000
$script:BMHardCap  = Get-BMSettingInt 'BM_HARD_CAP_MS' 8000
$script:BMBeatStaleS = Get-BMSettingInt 'BM_BEAT_STALE_S' 180
$script:BMUrl      = "http://$($script:BMHost):$($script:BMPort)/"

function Invoke-BMWsl {
  # WSL command with a HARD timeout so a frozen VM can never hang the caller.
  # NUL-stripped at the source (wsl.exe writes errors as UTF-16LE -> NUL-mangled text).
  [Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSUseUsingScopeModifierInNewRunspaces', '', Justification = 'Args passed via -ArgumentList/param(), not closure-captured.')]
  param([string]$Cmd, [int]$TimeoutSec = 20)
  $job = Start-Job { param($d, $c) & wsl.exe -d $d -e bash -lc "export PATH=`$HOME/.local/bin:`$PATH; $c" 2>&1 } -ArgumentList $script:BMDistro, $Cmd
  if (Wait-Job $job -Timeout $TimeoutSec) { $o = Receive-Job $job; Remove-Job $job -Force -ErrorAction SilentlyContinue; return (($o -join "`n") -replace "`0", '') }
  Stop-Job $job -ErrorAction SilentlyContinue; Remove-Job $job -Force -ErrorAction SilentlyContinue
  return '__WSL_TIMEOUT__'
}

function Test-BMHealth {
  # -> @{ State = HEALTHY|SLOW|DOWN ; Ms ; Http }  (direct HttpWebRequest, no curl chain)
  param([int]$SlowMs = $script:BMSlowMs, [int]$HardCapMs = $script:BMHardCap, [string]$Url = $script:BMUrl)
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

function Wait-BMAlive {
  param([int]$TimeoutSec = 150)
  # gradio init can take 90s+ on this box - readiness poll, not a blind sleep.
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  do { if ((Test-BMHealth).State -eq 'HEALTHY') { return $true }; Start-Sleep -Milliseconds 1000 } while ((Get-Date) -lt $deadline)
  return $false
}

function Get-BMWatchdogProcess {
  # Argument-shape detector (the cs lesson: substring match flags the probe's own shell).
  @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe' OR Name='pwsh.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -match '(?i)-File\s+"?[^"]*bm-watchdog\.ps1' })
}

function Format-BMProbeReply {
  param([string]$Text, [int]$Max = 120)
  if ($null -eq $Text) { return '' }
  $s = ($Text -replace "[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", '') -replace '\s+', ' '
  $s = $s.Trim()
  if ($s.Length -gt $Max) { $s = $s.Substring(0, $Max) + '...(truncated)' }
  return $s
}
