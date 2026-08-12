# cs-lib -- shared Claude Science config + health/probe helpers.
# Dot-sourced by cs.ps1, cs-doctor.ps1, cs-watchdog.ps1, cs-start.ps1, cs-recover.ps1,
# cs-tailscale-serve.ps1, install.ps1 and register-tasks.ps1 so the wedge-detection AND the
# configuration are identical everywhere (no drift). A wedged daemon (WSL frozen under host-RAM
# pressure) still ACCEPTS the socket but answers slowly/never -> latency is the signal the old
# any-HTTP-status probe missed.

# --- config: cs.conf (SSOT) -> in-script defaults, with env vars overriding both -------------
# Precedence is env > cs.conf > default. Parsing is deliberately trivial (KEY=VALUE, `#` comments)
# because the same file is `source`d verbatim by cs-lib.sh on the bash side; a richer format would
# need a parser on both halves. A missing/unreadable cs.conf is NOT fatal -- the defaults below are
# exactly the values these scripts shipped with, so the seam can never make the tool less available
# than it was before it existed.
$script:CSConfPath = Join-Path $PSScriptRoot 'cs.conf'
$script:CSConf = @{}
if (Test-Path $script:CSConfPath) {
  foreach ($line in (Get-Content -LiteralPath $script:CSConfPath -ErrorAction SilentlyContinue)) {
    $t = $line.Trim()
    if (-not $t -or $t.StartsWith('#')) { continue }
    $i = $t.IndexOf('=')
    if ($i -lt 1) { continue }
    $script:CSConf[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim()
  }
}
function Get-CSSetting {
  param([string]$Key, [string]$Default)
  $envVal = [Environment]::GetEnvironmentVariable($Key)
  if ($envVal) { return $envVal }
  if ($script:CSConf.ContainsKey($Key) -and $script:CSConf[$Key]) { return $script:CSConf[$Key] }
  return $Default
}
function Get-CSSettingInt {
  param([string]$Key, [int]$Default)
  $v = 0
  if ([int]::TryParse((Get-CSSetting $Key "$Default"), [ref]$v)) { return $v }
  return $Default
}

$script:CSHost          = Get-CSSetting    'CS_HOST'            '127.0.0.1'
$script:CSPort          = Get-CSSettingInt 'CS_PORT'            8000
$script:CSDistro        = Get-CSSetting    'CS_DISTRO'          'Ubuntu'
$script:CSSlowMs        = Get-CSSettingInt 'CS_SLOW_MS'         4000    # >= this = SLOW (wedge candidate)
$script:CSHardCap       = Get-CSSettingInt 'CS_HARD_CAP_MS'     8000    # ms socket/read timeout
$script:CSBackupRoot    = Get-CSSetting    'CS_BACKUP_ROOT'     '/mnt/d/Backups/claude-science'
$script:CSBackupKeyRoot = Get-CSSetting    'CS_BACKUP_KEY_ROOT' '/mnt/d/Backups/claude-science-keys'
$script:CSMinWslDiskGb  = Get-CSSettingInt 'CS_MIN_WSL_DISK_GB' 10
$script:CSMinHostRamGb  = Get-CSSettingInt 'CS_MIN_HOST_RAM_GB' 3
$script:CSBackupWarnH   = Get-CSSettingInt 'CS_BACKUP_WARN_H'   176
$script:CSBackupFailH   = Get-CSSettingInt 'CS_BACKUP_FAIL_H'   192
$script:CSBeatStaleS    = Get-CSSettingInt 'CS_BEAT_STALE_S'    180
$script:CSCommandsDir   = Get-CSSetting    'CS_COMMANDS_DIR'    '.claude/commands'
$script:CSUrl           = "http://$($script:CSHost):$($script:CSPort)/"
# Relative = under $HOME (the normal case, and the only portable way to express it in a KEY=VALUE
# file that bash also sources). An absolute override is honoured as-is so a test can point the
# slash-command route check at a scratch directory.
if (-not [System.IO.Path]::IsPathRooted($script:CSCommandsDir)) {
  $script:CSCommandsDir = Join-Path $HOME $script:CSCommandsDir
}

# --- fault injection: ARMED and always DISCLOSED -------------------------------------------------
# ROUND 1 SHIPPED THIS SEAM UNARMED AND UNMARKED, and an independent auditor proved the cost:
#   $env:CS_FORCE_WSL_DB='ok|wal|999M'  ->  "[+] DB PASS integrity=ok journal=wal size=999M",
#   "summary: 0 FAIL, 0 WARN, 0 NOT-CHECKED, 12 PASS", exit 0, and ZERO occurrences of the word
#   "inject" anywhere in the output. I reproduced that verbatim before changing anything.
# A health tool that can be told to print a fabricated green IS the gate-fabrication class this
# repo exists to catch, so the seam now carries two independent locks:
#   1. ARMED  - a CS_FORCE_* variable is ignored outright unless CS_FAULT_INJECTION=1. A stray or
#               leaked variable can no longer change one bit of behaviour. An ignored variable is
#               REPORTED (cs-doctor renders it FAIL), never silently swallowed - an unexplained
#               injection attempt in the environment is itself a finding.
#   2. MARKED - every value actually taken from injection is recorded below, so cs-doctor can
#               prefix those rows with [INJECTED] and emit a FAIL banner. An injected run can
#               therefore never render as a clean pass and never exit 0.
# The seam still has to exist: cs-doctor's fail-closed behaviour is unverifiable on a healthy box,
# and a probe that is silent in both states measures nothing.
$script:CSInjectionArmed = ($env:CS_FAULT_INJECTION -eq '1')
$script:CSInjectionUsed = [System.Collections.Generic.List[string]]::new()
$script:CSForceVars = @(
  @([Environment]::GetEnvironmentVariables().Keys) |
  Where-Object { "$_" -like 'CS_FORCE_*' } | Sort-Object
)

function Get-CSInjectionState {
  # -> @{ Armed; Declared[]; Used[]; Refused[]; Active } . `Refused` is non-empty exactly when
  # someone set a CS_FORCE_* without arming, which is the accident/tamper case.
  [pscustomobject]@{
    Armed    = $script:CSInjectionArmed
    Declared = @($script:CSForceVars)
    Used     = @($script:CSInjectionUsed | Sort-Object -Unique)
    Refused  = @(if ($script:CSInjectionArmed) { @() } else { $script:CSForceVars })
    Active   = ($script:CSInjectionArmed -and $script:CSForceVars.Count -gt 0)
  }
}

function Test-CSTagInjected {
  # Did THIS logical probe's value come from injection? Used to tag individual rows.
  param([string]$Tag)
  if (-not $Tag) { return $false }
  return ($script:CSInjectionUsed -contains 'CS_FORCE_WSL_TIMEOUT') -or
         ($script:CSInjectionUsed -contains "CS_FORCE_WSL_$($Tag.ToUpper())")
}

function ConvertTo-CSWindowsPath {
  # /mnt/d/Backups/x -> D:\Backups\x . The backup root lives in the config ONCE, in WSL form
  # (what the bash scripts need); this derives the Windows form instead of duplicating it.
  # Returns $null for anything that is not a /mnt/<drive>/... path, so callers fail closed
  # rather than inventing a path.
  param([string]$WslPath)
  $m = [regex]::Match($WslPath, '^/mnt/([a-zA-Z])(/.*)?$')
  if (-not $m.Success) { return $null }
  $tail = $m.Groups[2].Value -replace '/', '\'
  return ($m.Groups[1].Value.ToUpper() + ':' + $tail)
}
$script:CSBackupRootWin = ConvertTo-CSWindowsPath $script:CSBackupRoot

function Invoke-CSWsl {
  # Run a WSL login-shell command with a HARD timeout, so a frozen VM can never hang the caller.
  # Job inputs are passed explicitly via -ArgumentList and received through param($d,$c) below --
  # no closure capture, so $using: does not apply (PSSA false positive). Live-verified: cs status
  # gathers WSL pid/disk/RAM through this path correctly.
  #
  # -Tag names the logical probe (db|backup|...) so a test can inject ONE probe's reply without
  # touching the others. Injection is TEST-ONLY, requires CS_FAULT_INJECTION=1 to be armed, and
  # every use is recorded so the caller can disclose it (see the fault-injection block above).
  [Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSUseUsingScopeModifierInNewRunspaces', '', Justification = 'Args passed via -ArgumentList/param(), not closure-captured.')]
  param([string]$Cmd, [int]$TimeoutSec = 20, [string]$Tag)
  if ($script:CSInjectionArmed) {
    if ($env:CS_FORCE_WSL_TIMEOUT -eq '1') { $script:CSInjectionUsed.Add('CS_FORCE_WSL_TIMEOUT'); return '__WSL_TIMEOUT__' }
    if ($Tag) {
      $vn = "CS_FORCE_WSL_$($Tag.ToUpper())"
      $forced = [Environment]::GetEnvironmentVariable($vn)
      if ($forced) { $script:CSInjectionUsed.Add($vn); if ($forced -eq '__EMPTY__') { return '' } else { return $forced } }
    }
  }
  $job = Start-Job { param($d, $c) & wsl.exe -d $d -e bash -lc "export PATH=`$HOME/.local/bin:`$PATH; $c" 2>&1 } -ArgumentList $script:CSDistro, $Cmd
  # NUL-strip at the SOURCE. wsl.exe writes its own errors ("There is no distribution with the
  # supplied name.") as UTF-16LE; decoded as single-byte text every character is followed by a NUL,
  # so the reply reaches the report as "T h e r e   i s   n o ...". Removing the NULs here recovers
  # the real sentence for every caller at once, instead of each row learning to un-mangle it.
  # Only U+0000 is touched -- newlines and the payload are untouched, so sentinel comparisons and
  # the pipe-delimited probe replies below are unaffected.
  if (Wait-Job $job -Timeout $TimeoutSec) { $o = Receive-Job $job; Remove-Job $job -Force -ErrorAction SilentlyContinue; return (($o -join "`n") -replace "`0", '') }
  Stop-Job $job -ErrorAction SilentlyContinue; Remove-Job $job -Force -ErrorAction SilentlyContinue
  return '__WSL_TIMEOUT__'
}

function Get-CSWatchdogProcess {
  # The watchdog instances a doctor/status row should count.
  #
  # DETECTOR BUG THIS FIXES (measured 2026-08-12, twice, by two different agents): the previous
  # filter was `CommandLine -like '*cs-watchdog*'`, which MATCHES THE PROBE'S OWN SHELL whenever the
  # probing command line contains the string -- reporting 2 instances and a phantom "DUPLICATE -
  # dual-watchdog race" when exactly one watchdog was running. Excluding $PID is not enough either
  # (a parent pwsh running the probe is a different pid), so this also requires the `-File ...
  # cs-watchdog.ps1` ARGUMENT SHAPE that only a real launch has, not a bare substring.
  @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe' OR Name='pwsh.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -match '(?i)-File\s+"?[^"]*cs-watchdog\.ps1' })
}

function Test-CSEphemeralWorktree {
  # -> the `gitdir:` marker line if $Path lives inside a LINKED git worktree, else $null.
  #
  # WHY THIS EXISTS (measured 2026-08-12 by an independent verifier, reproduced by me).
  # ClaudeScienceWatchdog's action was
  #   -File "C:\Users\Prekzursil\source\ast-integrate\scripts\claude-science\cs-watchdog.ps1"
  # and `C:\Users\Prekzursil\source\ast-integrate\.git` is a FILE reading
  #   gitdir: C:/Users/Prekzursil/source/agent-skills-toolchain/.git/worktrees/ast-integrate
  # i.e. a linked worktree created for one integration run. `git worktree remove` deletes that
  # directory, and an always-on supervisor registered to launch out of it dies with it -- silently,
  # because Task Scheduler reports a missing script as a task that ran. Meanwhile the stable copy
  # ~/.local/bin/cs-watchdog.ps1 already existed, byte-identical, and nothing used it.
  #
  # A NORMAL CLONE IS NOT FLAGGED. There, `.git` is a DIRECTORY and the checkout is as durable as
  # ~/.local/bin; flagging it would be a false alarm on the ordinary developer layout. The property
  # that matters is "created and destroyed per run", and the linked-worktree marker is exactly that.
  #
  # `-Force` is not optional: `.git` is HIDDEN, and Get-Item without it throws "Could not find
  # item" on a path Get-Content reads fine -- a detector that reports "no worktree here" for every
  # repository on the box.
  param([string]$Path)
  if (-not $Path) { return $null }
  $dir = try { if (Test-Path -LiteralPath $Path -PathType Leaf) { Split-Path -Parent $Path } else { $Path } } catch { return $null }
  for ($i = 0; $i -lt 40 -and $dir; $i++) {
    $marker = Join-Path $dir '.git'
    $item = Get-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue
    if ($item) {
      if (-not $item.PSIsContainer) {
        $line = (Get-Content -LiteralPath $marker -TotalCount 1 -ErrorAction SilentlyContinue)
        if ("$line" -match '(?i)gitdir:.*[\\/]worktrees[\\/]') { return "$line".Trim() }
      }
      return $null   # a real .git directory (or a gitfile that is not a worktree) = durable
    }
    $parent = Split-Path -Parent $dir
    if ($parent -eq $dir) { break }
    $dir = $parent
  }
  return $null
}

function Get-CSWatchdogActionVerdict {
  # Does the registered watchdog task launch code that (a) exists, (b) will still exist tomorrow,
  # and (c) is the same code as this deploy? -> @{ Status; Detail }
  #
  # cs-doctor already checked the TRIGGER (the 3.3-day-death fix) and the PROCESS COUNT, and had a
  # 'Watchdog registered' row that read only $task.State. None of the three looks at what the task
  # actually RUNS, so a task pointing at a deleted or stale script reported PASS/PASS/PASS. Field
  # check with a control on the round-2 doctor: /\.Actions/ 0 hits, /cs-watchdog/ 0, /\.Triggers/ 1.
  #
  # Pure and injection-free ON PURPOSE: it takes the task object and a reference path, so the test
  # harness can drive every branch without touching Task Scheduler and without another CS_FORCE_*
  # seam (each of those is one more way to fabricate a green -- see the D2 disclosure above).
  param([object]$Task, [string]$ReferenceScript)
  if (-not $Task) { return @{ Status = 'FAIL'; Detail = 'no ClaudeScienceWatchdog task - run register-tasks.ps1' } }
  $act = @($Task.Actions)[0]
  if (-not $act) { return @{ Status = 'NOT-CHECKED'; Detail = 'task has no action to inspect' } }
  $m = [regex]::Match("$($act.Arguments)", '(?i)-File\s+"?([^"]+?\.ps1)"?(\s|$)')
  if (-not $m.Success) {
    return @{ Status = 'NOT-CHECKED'; Detail = "action names no -File script (execute=$($act.Execute)); launch target unverifiable" }
  }
  $target = $m.Groups[1].Value.Trim()
  if (-not (Test-Path -LiteralPath $target)) {
    return @{ Status = 'FAIL'; Detail = "launches a script that DOES NOT EXIST: $target - the watchdog cannot start at all. Re-run register-tasks.ps1" }
  }
  $wt = Test-CSEphemeralWorktree $target
  if ($wt) {
    return @{ Status = 'FAIL'; Detail = "launches out of an EPHEMERAL git worktree ($wt): $target - it dies when the worktree is removed. Re-run register-tasks.ps1 to point at ~/.local/bin" }
  }
  if (-not $ReferenceScript -or -not (Test-Path -LiteralPath $ReferenceScript)) {
    return @{ Status = 'PASS'; Detail = "$target (exists, durable; no reference copy to compare against)" }
  }
  $a = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
  $b = (Get-FileHash -LiteralPath $ReferenceScript -Algorithm SHA256).Hash
  if ($a -ne $b) {
    return @{ Status = 'FAIL'; Detail = "launches STALE code: $target (sha $($a.Substring(0,12))) != $ReferenceScript (sha $($b.Substring(0,12)))" }
  }
  return @{ Status = 'PASS'; Detail = "$target (durable, sha $($a.Substring(0,12)) matches this deploy)" }
}

function Format-CSProbeReply {
  # Make a raw probe reply safe to print in a one-line report cell.
  #
  # MEASURED 2026-08-12: the DB row rendered wsl.exe's own error as "T h e r e   i s   n o ..." --
  # wsl.exe emits its errors as UTF-16LE, and reading them as single-byte text interleaves a NUL
  # after every character. Stripping the NULs recovers the real sentence, which is the diagnosis
  # the operator needs; leaving them in produces a row that looks corrupted rather than informative.
  # Also bounds the length, because an unbounded reply pushes the rest of the table off-screen.
  param([string]$Text, [int]$Max = 140)
  if ($null -eq $Text) { return '' }
  $s = ($Text -replace "[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", '') -replace '\s+', ' '
  $s = $s.Trim()
  if ($s.Length -gt $Max) { $s = $s.Substring(0, $Max) + '...(truncated)' }
  return $s
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
