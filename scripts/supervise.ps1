<#
.SYNOPSIS
  supervise.ps1 - the estate's ONE shared supervision primitive.

.DESCRIPTION
  Replaces bespoke per-daemon watchdogs. Built 2026-09-25 because the estate had many
  hand-rolled watchdogs and no correct shared primitive, and it cost real availability:
  home's `rclone serve` on :2022/:2023 went down 2026-09-23 and stayed down for two days
  while the VM logged 649 "couldn't connect" errors that NOBODY SAW. The two defects that
  produced that outage are the two things this primitive is built around:

    1. a SILENT restart budget (a breaker that stops trying and only writes a log line), and
    2. a restart policy that cannot tell "dead" from "slow", so it either thrashes or gives up.

  FIVE PROPERTIES (each is separately provable - see supervise.selftest.ps1):

  (a) LIVENESS vs READINESS SPLIT. Liveness answers "is the process there". Readiness answers
      "is it serving". ONLY a liveness failure restarts by default. A merely-mute daemon is NOT
      a dead daemon: readiness failures are classified, and warmup + dependency + unknown
      failures NEVER restart. To restart on a wedge you need POSITIVE evidence of self-fault
      (readiness exit 1) sustained for -SelfFaultStrikes consecutive ticks.

  (b) EXPONENTIAL BACKOFF, CAPPED, WITH FULL JITTER.
        ceiling = min(BackoffCapMs, BackoffBaseMs * 2^(attempt-1))
        delay   = uniform[0, ceiling]            <- AWS "full jitter"
      Full jitter (not equal jitter, not none) because N supervisors restarting N units must
      not re-synchronise into a thundering herd. -JitterSeed makes it reproducible for tests;
      production leaves it unset and gets a time-seeded RNG.

  (c) SLIDING-WINDOW RESTART BUDGET WITH A HARD LATCH THAT ESCALATES AND NOTIFIES.
      OTP restart-intensity: more than -MaxRestarts within -WindowSec => LATCH.
      The latch does THREE things, and the third is the one the estate was missing:
        1. stops restarting (no thrash),
        2. runs -EscalateCommand - a DIFFERENT remediation, not another restart,
        3. NOTIFIES, and RE-notifies every -LatchRenotifySec for as long as it stays latched.
      A latch that notifies once and then goes quiet is how a dead service stays dead for two
      days. Latched state is only cleared by an operator: -ClearLatch.

  (d) EVIDENCE CAPTURE BEFORE THE KILL. Attribution after a kill is near-impossible: the
      cmdline, the RSS, the open ports and the log tail all die with the process. Every restart
      writes an evidence directory FIRST (process.json, ports.txt, log.tail, context.json) and
      only then stops the process. If evidence capture fails, the restart still proceeds - the
      supervisor is fail-open by construction.

  (e) DURABLE STATE AND AN OPERATOR-VISIBLE CHURN NUMBER. Restart history, attempt count and
      the latch live in a JSON file, so a supervisor that is itself restarted does not forget
      that it latched. churnTotal is mirrored to <Name>.churn as a bare integer so a statusline
      or HUD can read it with one file read.

  SAFETY. This primitive refuses to stop a process it did not itself start unless -AdoptPid is
  passed, and refuses outright to stop anything matching -ProtectedNameMatch (default: the
  agent fleet - claude/node/python/pwsh MCP processes). Killing the fleet has destroyed working
  capability on this estate before.

.PARAMETER Name
  Unit name. Keys the state file, the churn file and the evidence tree. Required.

.PARAMETER Once
  Run a single tick and exit. This is the scheduled-task shape.

.PARAMETER Watch
  Loop forever, sleeping -IntervalSec between ticks. The foreground/daemon shape.

.PARAMETER Status
  Print one operator line for the unit and exit. Read-only: never starts, stops or latches.

.PARAMETER ClearLatch
  Clear a latch and reset the restart window. The only way out of a latch.

.EXAMPLE
  # single tick, scheduled-task shape
  pwsh -NoProfile -File supervise.ps1 -Name rclone-sftp-c -Once `
       -PidFile C:\ProgramData\vm-link\serve-c.pid `
       -ProcessNameMatch '^rclone$' `
       -StartCommand C:\ProgramData\vm-link\serve.cmd `
       -ReadinessCommand pwsh -ReadinessArgs '-NoProfile','-File','probe-2022.ps1' `
       -LogFile C:\ProgramData\vm-link\serve-c2.log -Ports 2022 `
       -EscalateCommand pwsh -EscalateArgs '-NoProfile','-File','escalate-linkdown.ps1'

.EXAMPLE
  pwsh -NoProfile -File supervise.ps1 -Name rclone-sftp-c -Status
#>
[CmdletBinding(DefaultParameterSetName = 'Tick')]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[A-Za-z0-9._-]{1,64}$')][string]$Name,

    # --- modes -------------------------------------------------------------------------
    [switch]$Once,
    [switch]$Watch,
    [switch]$Status,
    [switch]$ClearLatch,
    [switch]$DryRun,

    # --- how the unit is started -------------------------------------------------------
    [string]$StartCommand,
    [string[]]$StartArgs = @(),
    [string]$WorkingDirectory,

    # --- LIVENESS: is the process there? -----------------------------------------------
    [string]$PidFile,
    # Guard against pid reuse: the live pid must ALSO match this process-name regex.
    [string]$ProcessNameMatch,

    # --- READINESS: is it serving? -----------------------------------------------------
    # Contract (exit code): 0=READY 1=SELF-FAULT(restartable) 2=DEPENDENCY 3=WARMUP
    #                       anything else = UNKNOWN. DEPENDENCY/WARMUP/UNKNOWN never restart.
    [string]$ReadinessCommand,
    [string[]]$ReadinessArgs = @(),
    [int]$ReadinessTimeoutSec = 15,
    [int]$WarmupGraceSec = 75,
    [int]$SelfFaultStrikes = 3,

    # --- backoff -----------------------------------------------------------------------
    [int]$BackoffBaseMs = 1000,
    [int]$BackoffCapMs = 300000,
    [Nullable[int]]$JitterSeed,

    # --- restart budget / latch --------------------------------------------------------
    [int]$MaxRestarts = 5,
    [int]$WindowSec = 900,
    [int]$LatchRenotifySec = 3600,
    [string]$EscalateCommand,
    [string[]]$EscalateArgs = @(),
    [string]$NotifyCommand,
    [string[]]$NotifyArgs = @(),

    # --- evidence ----------------------------------------------------------------------
    [string]$LogFile,
    [int]$LogTailLines = 200,
    [int[]]$Ports = @(),

    # --- loop / paths / safety ---------------------------------------------------------
    [int]$IntervalSec = 30,
    [string]$StateRoot,
    [string]$EvidenceRoot,
    [switch]$AdoptPid,
    [string]$ProtectedNameMatch = '^(claude|node|python|pythonw|pwsh|powershell|uv|uvx|npx|Code|ssh|sshd|tailscaled)$',
    [switch]$AllowProtectedKill
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ======================================================================================
# paths
# ======================================================================================
$SupRoot = if ($StateRoot) { $StateRoot } else { Join-Path $HOME '.agents\state\supervise' }
$EvRoot = if ($EvidenceRoot) { $EvidenceRoot } else { Join-Path $HOME '.agents\state\supervise\evidence' }
$StatePath = Join-Path $SupRoot "$Name.json"
$ChurnPath = Join-Path $SupRoot "$Name.churn"
$OwnPidPath = Join-Path $SupRoot "$Name.ownpid"
$EventLogPath = Join-Path $SupRoot "$Name.events.log"

foreach ($d in @($SupRoot, $EvRoot)) {
    if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}

function Get-SupNow { [DateTimeOffset]::UtcNow }
function Format-SupTime([DateTimeOffset]$t) { $t.ToString('o') }

# All persisted instants are UNIX EPOCH SECONDS (int64), never ISO strings. Measured 2026-09-25:
# ConvertFrom-Json silently converts an ISO-8601 string property into a [DateTime], so a value
# written as "2026-09-25T23:30:27.8862306+00:00" comes back as a DateTime whose [string] form is
# the culture-dependent "09/25/2026 23:30:27" - sub-second precision gone and the parse now
# depends on CurrentCulture. An integer has no such failure mode.
function Get-SupEpoch { [long][DateTimeOffset]::UtcNow.ToUnixTimeSeconds() }
function Format-SupEpoch([long]$e) {
    if ($e -le 0) { return '(never)' }
    [DateTimeOffset]::FromUnixTimeSeconds($e).UtcDateTime.ToString('yyyy-MM-ddTHH:mm:ssZ')
}

function Write-SupEvent {
    param([string]$Level, [string]$Message)
    $line = '{0} [{1}] {2} {3}' -f (Format-SupTime (Get-SupNow)), $Level, $Name, $Message
    try {
        # rotate at 4 MB - an unbounded append is how watchdog logs eat a disk
        if ((Test-Path -LiteralPath $EventLogPath) -and (Get-Item -LiteralPath $EventLogPath).Length -gt 4MB) {
            Move-Item -LiteralPath $EventLogPath -Destination "$EventLogPath.1" -Force
        }
        Add-Content -LiteralPath $EventLogPath -Value $line -Encoding utf8
    } catch { }
    Write-Host $line
}

# ======================================================================================
# durable state
# ======================================================================================
function New-SupState {
    [pscustomobject]@{
        schema          = 'supervise/2'
        name            = $Name
        restarts        = @()   # epoch seconds, sliding window
        attempt         = 0     # consecutive restart attempts (drives backoff)
        churnTotal      = 0     # lifetime restarts - the operator-visible number
        latched         = $false
        latchedAtEpoch  = 0
        latchReason     = ''
        lastNotifyEpoch = 0
        selfFaultRun    = 0     # consecutive readiness=SELF-FAULT ticks
        startedAtEpoch  = 0     # when WE last started the unit (warmup grace anchor)
        ownPid          = 0     # the pid WE started - kill guard
        lastVerdict     = ''
        lastAction      = ''
        lastTickEpoch   = 0
        notifyCount     = 0
    }
}

function Read-SupState {
    if (-not (Test-Path -LiteralPath $StatePath)) { return New-SupState }
    try {
        $raw = Get-Content -LiteralPath $StatePath -Raw -Encoding utf8
        if ([string]::IsNullOrWhiteSpace($raw)) { return New-SupState }
        $o = $raw | ConvertFrom-Json
        $s = New-SupState
        foreach ($p in $s.PSObject.Properties.Name) {
            if ($o.PSObject.Properties.Name -contains $p) { $s.$p = $o.$p }
        }
        # ConvertFrom-Json gives $null for [] - normalise so .Count is always safe, and coerce
        # to int64 so a hand-edited or legacy state file cannot poison the arithmetic.
        $rs = @()
        foreach ($r in @($s.restarts)) {
            $n = [long]0
            if ([long]::TryParse([string]$r, [ref]$n) -and $n -gt 0) { $rs += $n }
        }
        $s.restarts = $rs
        return $s
    } catch {
        # A corrupt state file must not wedge the supervisor. Fail OPEN, but say so loudly:
        # losing the latch silently is exactly the failure this primitive exists to prevent.
        Write-SupEvent 'WARN' "state file unreadable ($($_.Exception.Message)) - starting from a fresh state; a prior LATCH may have been lost"
        return New-SupState
    }
}

function Write-SupState($s) {
    $s.lastTickEpoch = Get-SupEpoch
    $tmp = "$StatePath.tmp"
    ($s | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $tmp -Encoding utf8
    Move-Item -LiteralPath $tmp -Destination $StatePath -Force
    # mirror churn as a bare integer: one cheap read for a statusline / HUD
    try { Set-Content -LiteralPath $ChurnPath -Value ([string]$s.churnTotal) -Encoding ascii } catch { }
}

# ======================================================================================
# (b) backoff: exponential, capped, FULL jitter
# ======================================================================================
$script:SupRng = if ($null -ne $JitterSeed) { [System.Random]::new([int]$JitterSeed) } else { [System.Random]::new() }

function Get-SupBackoffCeilingMs {
    param([int]$Attempt, [int]$BaseMs = $BackoffBaseMs, [int]$CapMs = $BackoffCapMs)
    if ($Attempt -lt 1) { $Attempt = 1 }
    # 2^(attempt-1) as a double so a large attempt cannot overflow into a negative int
    $raw = [double]$BaseMs * [Math]::Pow(2, $Attempt - 1)
    [int][Math]::Min([double]$CapMs, $raw)
}

function Get-SupBackoffDelayMs {
    param([int]$Attempt)
    $ceil = Get-SupBackoffCeilingMs -Attempt $Attempt
    if ($ceil -le 0) { return 0 }
    # full jitter: uniform over [0, ceiling]
    $script:SupRng.Next(0, $ceil + 1)
}

# ======================================================================================
# (c) sliding-window restart budget
# ======================================================================================
# Returns an INT, never an array.
#
# The previous version returned the array via `, $keep` and let callers do
# `@(Get-SupWindowRestarts ...).Count`. Measured 2026-09-25 on this box: that pattern yields
# **1 for every non-trivial length** (n=0,1,2,3,5 all counted as 1), because the comma operator
# wraps the array so the caller receives exactly one object. The latch therefore NEVER fired -
# with MaxRestarts=2 the check was permanently (1+1) > 2 = false. Caught only because the
# self-test asserted the latch, which is the whole argument for the self-test existing.
# Returning a scalar removes the failure class rather than working around it.
function Get-SupWindowRestartCount {
    param($State, [long]$NowEpoch)
    $cut = $NowEpoch - $WindowSec
    $n = 0
    foreach ($r in @($State.restarts)) { if ([long]$r -gt $cut) { $n++ } }
    [int]$n
}

function Test-SupBudgetExceeded {
    param($State, [long]$NowEpoch)
    # "one more restart now" would make the count (window + 1). Exceeded when that passes Max.
    ((Get-SupWindowRestartCount -State $State -NowEpoch $NowEpoch) + 1) -gt $MaxRestarts
}

# ======================================================================================
# (a) liveness and readiness
# ======================================================================================
function Get-SupLivePid {
    # Returns the pid if the unit is LIVE, else $null. Pid-reuse-guarded.
    if (-not $PidFile) { return $null }
    if (-not (Test-Path -LiteralPath $PidFile)) { return $null }
    $txt = ''
    try { $txt = (Get-Content -LiteralPath $PidFile -Raw -ErrorAction Stop).Trim() } catch { return $null }
    $thePid = 0
    if (-not [int]::TryParse($txt, [ref]$thePid) -or $thePid -le 0) { return $null }
    $p = Get-Process -Id $thePid -ErrorAction SilentlyContinue
    if (-not $p) { return $null }
    if ($ProcessNameMatch -and ($p.ProcessName -notmatch $ProcessNameMatch)) {
        # pid reuse: the slot is occupied by something else entirely. NOT our unit, and
        # emphatically not something to kill.
        Write-SupEvent 'WARN' "pid $thePid is '$($p.ProcessName)', not matching /$ProcessNameMatch/ - treating unit as DEAD and NOT touching that process"
        return $null
    }
    $thePid
}

function Invoke-SupReadiness {
    # Returns one of READY / SELF / DEPENDENCY / WARMUP / UNKNOWN / NONE
    if (-not $ReadinessCommand) { return @{ Class = 'NONE'; Code = $null } }
    try {
        $rp = @{ FilePath = $ReadinessCommand; PassThru = $true; WindowStyle = 'Hidden'; ErrorAction = 'Stop' }
        if ($ReadinessArgs -and $ReadinessArgs.Count) { $rp.ArgumentList = $ReadinessArgs }
        $p = Start-Process @rp
        if (-not $p.WaitForExit($ReadinessTimeoutSec * 1000)) {
            try { $p.Kill() } catch { }
            # A readiness probe that never returns says nothing about the unit - it says the
            # probe is broken. UNKNOWN, therefore never restartable.
            return @{ Class = 'UNKNOWN'; Code = 'timeout' }
        }
        $code = $p.ExitCode
        switch ($code) {
            0 { return @{ Class = 'READY'; Code = 0 } }
            1 { return @{ Class = 'SELF'; Code = 1 } }
            2 { return @{ Class = 'DEPENDENCY'; Code = 2 } }
            3 { return @{ Class = 'WARMUP'; Code = 3 } }
            default { return @{ Class = 'UNKNOWN'; Code = $code } }
        }
    } catch {
        return @{ Class = 'UNKNOWN'; Code = "probe-error: $($_.Exception.Message)" }
    }
}

function Resolve-SupVerdict {
    <#
      The policy table. PURE - no side effects - so it is unit-testable in isolation.
        liveness  readiness    warmup?   =>  verdict            restart?
        DEAD      -            -             DEAD               yes
        ALIVE     NONE/READY   -             HEALTHY            no
        ALIVE     WARMUP       -             WARMING            no
        ALIVE     any-notready in grace      WARMING            no
        ALIVE     DEPENDENCY   past grace    DEGRADED-DEPENDENCY no  (+notify)
        ALIVE     UNKNOWN      past grace    DEGRADED-UNKNOWN   no  (+notify)
        ALIVE     SELF         past grace    WEDGED             only after N strikes
    #>
    param(
        [bool]$Alive,
        [string]$ReadinessClass,
        [bool]$InWarmup,
        [int]$SelfFaultRun
    )
    if (-not $Alive) { return @{ Verdict = 'DEAD'; Restart = $true; Notify = $false } }
    if ($ReadinessClass -in @('NONE', 'READY')) { return @{ Verdict = 'HEALTHY'; Restart = $false; Notify = $false } }
    if ($ReadinessClass -eq 'WARMUP') { return @{ Verdict = 'WARMING'; Restart = $false; Notify = $false } }
    if ($InWarmup) { return @{ Verdict = 'WARMING'; Restart = $false; Notify = $false } }
    switch ($ReadinessClass) {
        'DEPENDENCY' { return @{ Verdict = 'DEGRADED-DEPENDENCY'; Restart = $false; Notify = $true } }
        'SELF' {
            if ($SelfFaultRun -ge $SelfFaultStrikes) { return @{ Verdict = 'WEDGED'; Restart = $true; Notify = $true } }
            return @{ Verdict = 'SELF-FAULT-PENDING'; Restart = $false; Notify = $false }
        }
        default { return @{ Verdict = 'DEGRADED-UNKNOWN'; Restart = $false; Notify = $true } }
    }
}

# ======================================================================================
# (d) evidence capture - ALWAYS before the kill
# ======================================================================================
function Save-SupEvidence {
    param([Nullable[int]]$TargetPid, [string]$Reason, $State, $Extra)
    $stamp = (Get-SupNow)
    $dir = Join-Path (Join-Path $EvRoot $Name) ($stamp.ToString('yyyy-MM-dd'))
    $dir = Join-Path $dir ('{0}-{1}' -f $stamp.ToString('HHmmss'), ($Reason -replace '[^A-Za-z0-9-]', '_'))
    try {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null

        # --- process: cmdline + RSS + start time + parent. All of this dies with the kill.
        $proc = @{ pid = $TargetPid; captured = Format-SupTime $stamp }
        if ($TargetPid) {
            try {
                $p = Get-Process -Id $TargetPid -ErrorAction Stop
                $proc.name = $p.ProcessName
                $proc.workingSet64 = $p.WorkingSet64
                $proc.privateMemory64 = $p.PrivateMemorySize64
                $proc.handles = $p.HandleCount
                $proc.threads = $p.Threads.Count
                try { $proc.cpuSeconds = [Math]::Round($p.TotalProcessorTime.TotalSeconds, 2) } catch { }
                try { $proc.startTime = $p.StartTime.ToString('o') } catch { }
            } catch { $proc.processError = $_.Exception.Message }
            try {
                $ci = Get-CimInstance Win32_Process -Filter "ProcessId=$TargetPid" -ErrorAction Stop
                if ($ci) {
                    $proc.commandLine = $ci.CommandLine
                    $proc.parentProcessId = $ci.ParentProcessId
                    $proc.executablePath = $ci.ExecutablePath
                }
            } catch { $proc.cimError = $_.Exception.Message }
        }
        ($proc | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath (Join-Path $dir 'process.json') -Encoding utf8

        # --- ports: which sockets existed at capture time
        $portLines = @()
        foreach ($prt in @($Ports)) {
            try {
                $c = Get-NetTCPConnection -LocalPort $prt -ErrorAction SilentlyContinue |
                    Select-Object -First 20 LocalAddress, LocalPort, RemoteAddress, RemotePort, State, OwningProcess
                if ($c) { $portLines += ($c | Format-Table -AutoSize | Out-String) }
                else { $portLines += "port $prt : NO CONNECTION/LISTENER" }
            } catch { $portLines += "port $prt : probe error $($_.Exception.Message)" }
        }
        if (-not $portLines) { $portLines = @('(no -Ports declared)') }
        $portLines | Set-Content -LiteralPath (Join-Path $dir 'ports.txt') -Encoding utf8

        # --- log tail
        if ($LogFile -and (Test-Path -LiteralPath $LogFile)) {
            try {
                Get-Content -LiteralPath $LogFile -Tail $LogTailLines -ErrorAction Stop |
                    Set-Content -LiteralPath (Join-Path $dir 'log.tail') -Encoding utf8
            } catch {
                "log tail failed: $($_.Exception.Message)" | Set-Content -LiteralPath (Join-Path $dir 'log.tail') -Encoding utf8
            }
        }

        # --- context: the decision, the budget, the host
        $ctx = @{
            reason           = $Reason
            capturedAt       = Format-SupTime $stamp
            attempt          = $State.attempt
            churnTotal       = $State.churnTotal
            latched          = $State.latched
            restartsInWindow = Get-SupWindowRestartCount -State $State -NowEpoch (Get-SupEpoch)
            windowSec        = $WindowSec
            maxRestarts      = $MaxRestarts
            extra            = $Extra
        }
        try {
            $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
            $ctx.hostFreeRamGB = [Math]::Round($os.FreePhysicalMemory / 1MB, 2)
            $ctx.hostTotalRamGB = [Math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
        } catch { }
        ($ctx | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath (Join-Path $dir 'context.json') -Encoding utf8

        Write-SupEvent 'INFO' "evidence captured BEFORE action -> $dir"
        return $dir
    } catch {
        # Evidence is diagnostics, not a gate. Never let it block remediation.
        Write-SupEvent 'WARN' "evidence capture failed (continuing): $($_.Exception.Message)"
        return $null
    }
}

# ======================================================================================
# notify + escalate
# ======================================================================================
function Invoke-SupNotify {
    param([string]$Reason, [string]$Detail, $State, [switch]$Force)
    $nowE = Get-SupEpoch
    if (-not $Force -and [long]$State.lastNotifyEpoch -gt 0) {
        if (($nowE - [long]$State.lastNotifyEpoch) -lt $LatchRenotifySec) { return $false }
    }
    $msg = "NOTIFY [$Reason] $Name : $Detail (churnTotal=$($State.churnTotal))"
    Write-SupEvent 'ALERT' $msg
    $nf = Join-Path $SupRoot "$Name.notify.log"
    try { Add-Content -LiteralPath $nf -Value ('{0} {1}' -f (Format-SupEpoch $nowE), $msg) -Encoding utf8 } catch { }
    if ($NotifyCommand) {
        try {
            $args2 = @($NotifyArgs) + @($Name, $Reason, $Detail)
            Start-Process -FilePath $NotifyCommand -ArgumentList $args2 -WindowStyle Hidden -ErrorAction Stop | Out-Null
        } catch { Write-SupEvent 'WARN' "notify command failed: $($_.Exception.Message)" }
    }
    $State.lastNotifyEpoch = $nowE
    $State.notifyCount = [int]$State.notifyCount + 1
    $true
}

function Invoke-SupEscalate {
    param([string]$Reason, $State)
    if (-not $EscalateCommand) {
        Write-SupEvent 'WARN' "no -EscalateCommand configured - latch will notify only. A latch with no escalation is the rclone-serve failure mode."
        return $false
    }
    if ($DryRun) { Write-SupEvent 'INFO' "DRYRUN escalate: $EscalateCommand $($EscalateArgs -join ' ')"; return $true }
    try {
        $args2 = @($EscalateArgs) + @($Name, $Reason)
        Start-Process -FilePath $EscalateCommand -ArgumentList $args2 -WindowStyle Hidden -ErrorAction Stop | Out-Null
        Write-SupEvent 'INFO' "escalation dispatched: $EscalateCommand"
        return $true
    } catch {
        Write-SupEvent 'WARN' "escalation failed: $($_.Exception.Message)"
        return $false
    }
}

# ======================================================================================
# stop / start  (kill guard lives here)
# ======================================================================================
function Stop-SupUnit {
    param([int]$TargetPid, $State)
    $p = Get-Process -Id $TargetPid -ErrorAction SilentlyContinue
    if (-not $p) { return $true }

    if (($p.ProcessName -match $ProtectedNameMatch) -and -not $AllowProtectedKill) {
        Write-SupEvent 'REFUSE' "pid $TargetPid is '$($p.ProcessName)', matched by -ProtectedNameMatch. REFUSING to stop it (pass -AllowProtectedKill to override). The agent/MCP fleet is never a supervision victim."
        return $false
    }
    if (-not $AdoptPid -and ([int]$State.ownPid -gt 0) -and ([int]$State.ownPid -ne $TargetPid)) {
        Write-SupEvent 'REFUSE' "pid $TargetPid was not started by this supervisor (ownPid=$($State.ownPid)). REFUSING (pass -AdoptPid to override)."
        return $false
    }
    if ($DryRun) { Write-SupEvent 'INFO' "DRYRUN stop pid $TargetPid ($($p.ProcessName))"; return $true }
    try {
        Stop-Process -Id $TargetPid -Force -ErrorAction Stop
        Write-SupEvent 'INFO' "stopped pid $TargetPid ($($p.ProcessName))"
        return $true
    } catch {
        Write-SupEvent 'WARN' "stop pid $TargetPid failed: $($_.Exception.Message)"
        return $false
    }
}

function Start-SupUnit {
    param($State)
    if (-not $StartCommand) { Write-SupEvent 'WARN' 'no -StartCommand configured - cannot start'; return $null }
    if ($DryRun) { Write-SupEvent 'INFO' "DRYRUN start: $StartCommand $($StartArgs -join ' ')"; return -1 }
    try {
        $sp = @{ FilePath = $StartCommand; PassThru = $true; WindowStyle = 'Hidden'; ErrorAction = 'Stop' }
        if ($StartArgs -and $StartArgs.Count) { $sp.ArgumentList = $StartArgs }
        if ($WorkingDirectory) { $sp.WorkingDirectory = $WorkingDirectory }
        $p = Start-Process @sp
        Write-SupEvent 'INFO' "started pid $($p.Id): $StartCommand $($StartArgs -join ' ')"
        try { Set-Content -LiteralPath $OwnPidPath -Value ([string]$p.Id) -Encoding ascii } catch { }
        return $p.Id
    } catch {
        Write-SupEvent 'WARN' "start failed: $($_.Exception.Message)"
        return $null
    }
}

# ======================================================================================
# one tick
# ======================================================================================
function Invoke-SupTick {
    $s = Read-SupState
    $nowE = Get-SupEpoch

    $livePid = Get-SupLivePid
    $alive = $null -ne $livePid

    # warmup grace is anchored on OUR last start, so a unit we just launched is never
    # judged not-ready before it has had a chance to bind
    $inWarmup = $false
    if ([long]$s.startedAtEpoch -gt 0) {
        $inWarmup = ($nowE - [long]$s.startedAtEpoch) -lt $WarmupGraceSec
    }

    $rd = if ($alive) { Invoke-SupReadiness } else { @{ Class = 'NONE'; Code = $null } }
    if ($rd.Class -eq 'SELF') { $s.selfFaultRun = [int]$s.selfFaultRun + 1 } else { $s.selfFaultRun = 0 }

    $v = Resolve-SupVerdict -Alive $alive -ReadinessClass $rd.Class -InWarmup $inWarmup -SelfFaultRun ([int]$s.selfFaultRun)
    $s.lastVerdict = $v.Verdict

    Write-SupEvent 'INFO' ("tick verdict=$($v.Verdict) alive=$alive pid=$livePid readiness=$($rd.Class)/$($rd.Code) warmup=$inWarmup selfFaultRun=$($s.selfFaultRun) churn=$($s.churnTotal) latched=$($s.latched)")

    # ---- healthy: decay the backoff attempt counter, clear notify throttle -------------
    if ($v.Verdict -in @('HEALTHY')) {
        $s.attempt = 0
        $s.lastAction = 'none'
        Write-SupState $s
        return @{ Verdict = $v.Verdict; Action = 'none'; State = $s }
    }

    if (-not $v.Restart) {
        # (a) THE CORE REFUSAL. Alive but not serving => we do NOT restart. We notify.
        $s.lastAction = 'no-restart'
        if ($v.Notify) {
            [void](Invoke-SupNotify -Reason $v.Verdict -Detail "alive (pid $livePid) but not ready [$($rd.Class)/$($rd.Code)] - NOT restarting: a mute daemon is not a dead daemon" -State $s)
        }
        Write-SupState $s
        return @{ Verdict = $v.Verdict; Action = 'no-restart'; State = $s }
    }

    # ---- latched already? keep refusing, but KEEP TALKING -----------------------------
    if ($s.latched) {
        $s.lastAction = 'latched-refused'
        [void](Invoke-SupNotify -Reason 'LATCHED' -Detail "still latched since $(Format-SupEpoch ([long]$s.latchedAtEpoch)) ($($s.latchReason)); verdict=$($v.Verdict). Restart budget exhausted - operator action required: supervise.ps1 -Name $Name -ClearLatch" -State $s)
        Write-SupState $s
        return @{ Verdict = $v.Verdict; Action = 'latched-refused'; State = $s }
    }

    # ---- (c) budget check BEFORE spending a restart ------------------------------------
    if (Test-SupBudgetExceeded -State $s -NowEpoch $nowE) {
        $inWin = Get-SupWindowRestartCount -State $s -NowEpoch $nowE
        $s.latched = $true
        $s.latchedAtEpoch = $nowE
        $s.latchReason = "restart budget exhausted: $inWin restarts in ${WindowSec}s (max $MaxRestarts)"
        $s.lastAction = 'latched'
        [void](Save-SupEvidence -TargetPid $livePid -Reason 'latch' -State $s -Extra @{ verdict = $v.Verdict; readiness = $rd })
        # ESCALATE to a DIFFERENT remediation, and NOTIFY - never a silent stop.
        [void](Invoke-SupEscalate -Reason $s.latchReason -State $s)
        [void](Invoke-SupNotify -Reason 'LATCH' -Detail $s.latchReason -State $s -Force)
        Write-SupState $s
        return @{ Verdict = $v.Verdict; Action = 'latched'; State = $s }
    }

    # ---- (d) evidence FIRST, then the kill, then the restart --------------------------
    $s.attempt = [int]$s.attempt + 1
    $evDir = Save-SupEvidence -TargetPid $livePid -Reason $v.Verdict -State $s -Extra @{ readiness = $rd; attempt = $s.attempt }

    if ($alive -and $livePid) {
        if (-not (Stop-SupUnit -TargetPid $livePid -State $s)) {
            # refused by the kill guard - do NOT spend a restart or claim one happened
            $s.attempt = [int]$s.attempt - 1
            $s.lastAction = 'stop-refused'
            [void](Invoke-SupNotify -Reason 'STOP-REFUSED' -Detail "verdict=$($v.Verdict) but the kill guard refused pid $livePid" -State $s)
            Write-SupState $s
            return @{ Verdict = $v.Verdict; Action = 'stop-refused'; State = $s }
        }
    }

    # ---- (b) backoff before the restart ------------------------------------------------
    $delay = Get-SupBackoffDelayMs -Attempt $s.attempt
    Write-SupEvent 'INFO' ("backoff attempt=$($s.attempt) ceiling=$(Get-SupBackoffCeilingMs -Attempt $s.attempt)ms jittered=${delay}ms")
    if ($delay -gt 0 -and -not $DryRun) { Start-Sleep -Milliseconds $delay }

    $newPid = Start-SupUnit -State $s
    $s.restarts = @(@($s.restarts) + @([long](Get-SupEpoch)))
    $s.churnTotal = [int]$s.churnTotal + 1
    $s.startedAtEpoch = Get-SupEpoch
    $s.ownPid = $(if ($null -eq $newPid) { 0 } else { [int]$newPid })
    $s.lastAction = 'restarted'
    $s.selfFaultRun = 0
    Write-SupState $s
    Write-SupEvent 'INFO' "restarted (attempt=$($s.attempt) newPid=$newPid churnTotal=$($s.churnTotal) backoffMs=$delay evidence=$evDir)"
    return @{ Verdict = $v.Verdict; Action = 'restarted'; State = $s; BackoffMs = $delay; NewPid = $newPid }
}

# ======================================================================================
# entry points
# ======================================================================================
if ($ClearLatch) {
    $s = Read-SupState
    $was = $s.latched
    $s.latched = $false; $s.latchedAtEpoch = 0; $s.latchReason = ''
    $s.restarts = @(); $s.attempt = 0; $s.selfFaultRun = 0; $s.lastNotifyEpoch = 0
    Write-SupState $s
    Write-SupEvent 'INFO' "latch cleared (was latched=$was); restart window reset"
    Write-Host "SUCCESS:supervise/$Name latch-cleared was=$was"
    exit 0
}

if ($Status) {
    $s = Read-SupState
    $live = $null; try { $live = Get-SupLivePid } catch { }
    $inWin = Get-SupWindowRestartCount -State $s -NowEpoch (Get-SupEpoch)
    Write-Host ("supervise/{0}: live={1} pid={2} verdict={3} action={4} churnTotal={5} restartsInWindow={6}/{7} latched={8}{9} lastTick={10}" -f `
            $Name, ($null -ne $live), $live, $s.lastVerdict, $s.lastAction, $s.churnTotal, $inWin, $MaxRestarts, $s.latched,
        $(if ($s.latched) { " (since $(Format-SupEpoch ([long]$s.latchedAtEpoch)): $($s.latchReason))" } else { '' }),
        (Format-SupEpoch ([long]$s.lastTickEpoch)))
    exit $(if ($s.latched) { 3 } else { 0 })
}

if ($Watch) {
    Write-SupEvent 'INFO' "watch loop starting (interval=${IntervalSec}s maxRestarts=$MaxRestarts/${WindowSec}s backoff=${BackoffBaseMs}..${BackoffCapMs}ms fulljitter)"
    while ($true) {
        try { [void](Invoke-SupTick) } catch { Write-SupEvent 'WARN' "tick error (fail-open): $($_.Exception.Message)" }
        Start-Sleep -Seconds $IntervalSec
    }
}

# default: one tick
$r = Invoke-SupTick
Write-Host ("SUCCESS:supervise/{0} verdict={1} action={2} churnTotal={3}" -f $Name, $r.Verdict, $r.Action, $r.State.churnTotal)
exit $(if ($r.State.latched) { 3 } else { 0 })
