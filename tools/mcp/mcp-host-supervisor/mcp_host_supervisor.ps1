<#
.SYNOPSIS
    Always-on supervisor for a FLEET of shared mcp-http-host processes.

.DESCRIPTION
    Keeps exactly ONE `mcp_http_host.py` per enabled server in fleet.json alive on its
    loopback port, so every Claude Code / Codex session dials the same shared instance
    instead of spawning its own stdio child.

    Mirrors MCPAgentMailSupervisor (named mutex, health gate, backoff, rotating log)
    and adds the two things that supervisor lacks:

      * ORPHAN REAPING (ownership-scoped). A machine-wide pattern reap once killed
        sibling sessions' MCP children. Here a process is killed only when it is OUR
        untracked leftover or its parent is gone - never because it merely matches a
        pattern. The decision is made by `fleet.py orphans`, which is unit-tested
        against exactly that regression.

      * CPU-PROGRESS WEDGE DETECTION (AND-gate). Recycling on a failed health poll
        ALONE is what made the agent-mail supervisor kill children 2-60s before they
        bound. A recycle here needs three agreeing signals - unhealthy, CPU flat, and
        the host's own `requests_served` flat. `fleet.py verdict` decides; five
        mutation tests prove the suite catches the weakened forms.

    ALL decision logic lives in the tested `fleet.py`; this script only actuates.

.PARAMETER Manifest     Path to fleet.json. Default: ./fleet.json beside this script.
.PARAMETER Once         Run a single ensure-pass and exit (task-triggered / testing).
.PARAMETER DryRun       Report what WOULD happen; never spawn, never kill.
.PARAMETER StopExisting Stop supervisor-owned hosts, release the mutex, exit.

.NOTES
    Bind is loopback-only (fleet.py rejects anything else).
    Never edits ~/.claude.json - registration is apply-when-closed via
    ../mcp-http-host/apply_registration.py.
#>
[CmdletBinding()]
param(
    [string]$Manifest = (Join-Path $PSScriptRoot 'fleet.json'),
    [string]$PythonExe = 'C:/Python314/python.exe',
    [switch]$Once,
    [switch]$DryRun,
    [switch]$StopExisting
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# --------------------------------------------------------------------------- config
$FleetPy      = Join-Path $PSScriptRoot 'fleet.py'
$HostPy       = Join-Path $PSScriptRoot '../mcp-http-host/mcp_http_host.py'
$LogDir       = Join-Path $PSScriptRoot 'logs'
$LogFile      = Join-Path $LogDir 'mcp_host_supervisor.log'
$StateFile    = Join-Path $LogDir 'supervisor_state.json'
$MutexName    = 'Global\mcp_host_supervisor'
$ReapSignature = 'mcp_http_host.py'
$MaxLogBytes  = 5MB

$HealthPollSec  = 10    # steady-state re-check cadence
$BackoffMin     = 2
$BackoffMax     = 60
$MaxFailStreak  = 3     # failed polls before a RUNNING host is even considered wedged

# --------------------------------------------------------------------------- logging
function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = ('{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message)
    try {
        if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
        if ((Test-Path $LogFile) -and ((Get-Item $LogFile).Length -gt $MaxLogBytes)) {
            Move-Item -Force -Path $LogFile -Destination "$LogFile.1"
        }
        Add-Content -Path $LogFile -Value $line -Encoding utf8
    } catch { }
    Write-Host $line
}

# --------------------------------------------------------------------------- helpers
function Invoke-Fleet {
    <# Shell to the tested decision module and parse its JSON verdict. #>
    param([string[]]$FleetArgs)
    $raw = & $PythonExe $FleetPy @FleetArgs 2>&1
    $text = ($raw | Out-String).Trim()
    $jsonLine = ($text -split "`n" | Where-Object { $_.TrimStart().StartsWith('{') } | Select-Object -Last 1)
    if (-not $jsonLine) { return $null }
    try { return $jsonLine | ConvertFrom-Json } catch { return $null }
}

function Get-HealthSample {
    <# Probe /healthz. Bypass any system proxy - Fiddler otherwise 502s loopback. #>
    param([string]$Url, [int]$TimeoutSec = 8)
    try {
        $handler = [System.Net.Http.HttpClientHandler]::new()
        $handler.UseProxy = $false
        $client = [System.Net.Http.HttpClient]::new($handler)
        $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSec)
        $resp = $client.GetAsync($Url).GetAwaiter().GetResult()
        $body = $resp.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        $client.Dispose(); $handler.Dispose()
        if ([int]$resp.StatusCode -eq 200) { return ($body | ConvertFrom-Json) }
    } catch { }
    return $null
}

function Get-ProcSnapshot {
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
        ForEach-Object {
            [pscustomobject]@{
                pid     = [int]$_.ProcessId
                ppid    = [int]$_.ParentProcessId
                cmdline = [string]$_.CommandLine
            }
        }
}

function Get-CpuSeconds {
    param([int]$ProcessId)
    try { return (Get-Process -Id $ProcessId -ErrorAction Stop).TotalProcessorTime.TotalSeconds }
    catch { return 0.0 }
}

function Read-State {
    if (Test-Path $StateFile) {
        try { return (Get-Content $StateFile -Raw | ConvertFrom-Json -AsHashtable) } catch { }
    }
    return @{}
}

function Save-State {
    param([hashtable]$State)
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
    $State | ConvertTo-Json -Depth 6 | Set-Content -Path $StateFile -Encoding utf8
}

function New-TrackedEntry {
    param([int]$TrackedPid, [int]$FailStreak = 0, [double]$Cpu = 0.0, [int]$Served = 0, [string]$StartedAt)
    if (-not $StartedAt) { $StartedAt = (Get-Date).ToString('o') }
    return @{
        pid = $TrackedPid; fail_streak = $FailStreak; cpu_seconds = $Cpu
        requests_served = $Served; started_at = $StartedAt
    }
}

# --------------------------------------------------------------------------- lifecycle
function Start-SharedHost {
    param($Entry)
    if ($DryRun) { Write-Log "DRY-RUN would start $($Entry.name) on :$($Entry.port)"; return 0 }
    $hostArgs = @($HostPy, '--eager', '--host', $Entry.bind_host, '--port', $Entry.port, '--') + $Entry.command
    $proc = Start-Process -FilePath $PythonExe -ArgumentList $hostArgs `
        -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
    Write-Log "started $($Entry.name) pid=$($proc.Id) on :$($Entry.port)"
    return [int]$proc.Id
}

function Stop-HostPid {
    param([int]$ProcessId, [string]$Why)
    if ($ProcessId -le 0) { return }
    if ($DryRun) { Write-Log "DRY-RUN would stop pid=$ProcessId ($Why)"; return }
    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
        Write-Log "stopped pid=$ProcessId ($Why)" 'WARN'
    } catch {
        Write-Log "could not stop pid=${ProcessId}: $_" 'WARN'
    }
}

function Invoke-Reap {
    <# Ownership-scoped orphan reap. NEVER a machine-wide pattern kill. #>
    param([int[]]$TrackedPids)
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
    $payload = @{
        supervisor_pid = $PID
        tracked_pids   = @($TrackedPids)
        signature      = $ReapSignature
        procs          = @(Get-ProcSnapshot)
    }
    $tmp = Join-Path $LogDir 'reap_input.json'
    $payload | ConvertTo-Json -Depth 6 | Set-Content -Path $tmp -Encoding utf8
    $result = Invoke-Fleet @('orphans', '--input', $tmp)
    if ($null -eq $result -or -not $result.ok) { Write-Log 'orphan probe failed; reaping nothing' 'WARN'; return }
    foreach ($orphanPid in @($result.orphans)) {
        Stop-HostPid -ProcessId ([int]$orphanPid) -Why 'orphaned shared host'
    }
}

# --------------------------------------------------------------------------- main pass
function Invoke-EnsurePass {
    param($Plan, [hashtable]$State)

    $tracked = [System.Collections.Generic.List[int]]::new()
    foreach ($entry in $Plan) {
        $name  = $entry.name
        $prior = if ($State.ContainsKey($name)) { $State[$name] } else { $null }

        $health = Get-HealthSample -Url $entry.health_url

        # A healthy endpoint is ADOPTED whoever owns it - never double-bind a live port.
        if ($null -ne $health) {
            $hostPid = [int]$health.host_pid
            $tracked.Add($hostPid)
            if ([int]$health.child_spawn_count -gt 1) {
                Write-Log "$name child_spawn_count=$($health.child_spawn_count) (child restarted)" 'WARN'
            }
            $startedAt = if ($prior) { [string]$prior.started_at } else { $null }
            $State[$name] = New-TrackedEntry -TrackedPid $hostPid `
                -Cpu (Get-CpuSeconds -ProcessId $hostPid) `
                -Served ([int]$health.requests_served) -StartedAt $startedAt
            continue
        }

        # Unhealthy and never started (or lost): start it.
        if ($null -eq $prior -or [int]$prior.pid -le 0) {
            $newPid = Start-SharedHost -Entry $entry
            if ($newPid -gt 0) { $tracked.Add($newPid) }
            $State[$name] = New-TrackedEntry -TrackedPid $newPid
            continue
        }

        $hostPid = [int]$prior.pid
        if ($null -eq (Get-Process -Id $hostPid -ErrorAction SilentlyContinue)) {
            Write-Log "$name pid=$hostPid is gone; restarting" 'WARN'
            $newPid = Start-SharedHost -Entry $entry
            if ($newPid -gt 0) { $tracked.Add($newPid) }
            $State[$name] = New-TrackedEntry -TrackedPid $newPid
            continue
        }

        $tracked.Add($hostPid)
        $streak = [int]$prior.fail_streak + 1
        $uptime = ((Get-Date) - [datetime]::Parse([string]$prior.started_at)).TotalSeconds
        $cpuNow = Get-CpuSeconds -ProcessId $hostPid
        $probe  = @{
            startup_grace_sec = $entry.startup_grace_sec
            max_fail_streak   = $MaxFailStreak
            previous = @{
                cpu_seconds = [double]$prior.cpu_seconds; requests_served = [int]$prior.requests_served
                healthy = $false; uptime_sec = $uptime; fail_streak = $streak
            }
            current = @{
                cpu_seconds = $cpuNow; requests_served = [int]$prior.requests_served
                healthy = $false; uptime_sec = $uptime; fail_streak = $streak
            }
        }
        $tmp = Join-Path $LogDir 'verdict_input.json'
        $probe | ConvertTo-Json -Depth 6 | Set-Content -Path $tmp -Encoding utf8
        $verdict = Invoke-Fleet @('verdict', '--state', $tmp)
        $label = if ($verdict) { [string]$verdict.verdict } else { 'DEGRADED' }
        Write-Log "$name unhealthy streak=$streak uptime=$([int]$uptime)s cpu=$([math]::Round($cpuNow,1))s -> $label"

        if ($label -eq 'WEDGED') {
            Stop-HostPid -ProcessId $hostPid -Why 'WEDGED (unhealthy + CPU flat + requests flat)'
            $newPid = Start-SharedHost -Entry $entry
            $State[$name] = New-TrackedEntry -TrackedPid $newPid
        } else {
            $State[$name] = New-TrackedEntry -TrackedPid $hostPid -FailStreak $streak `
                -Cpu $cpuNow -Served ([int]$prior.requests_served) -StartedAt ([string]$prior.started_at)
        }
    }

    Invoke-Reap -TrackedPids $tracked.ToArray()
    return $State
}

# --------------------------------------------------------------------------- entry
$mutex = [System.Threading.Mutex]::new($false, $MutexName)
if (-not $mutex.WaitOne(0)) {
    Write-Log 'another supervisor already holds the mutex; exiting' 'WARN'
    exit 0
}

try {
    if (-not (Test-Path $Manifest)) { Write-Log "manifest not found: $Manifest" 'ERROR'; exit 2 }

    $planResult = Invoke-Fleet @('plan', '--manifest', $Manifest)
    if ($null -eq $planResult -or -not $planResult.ok) {
        Write-Log 'manifest INVALID - refusing to start anything:' 'ERROR'
        if ($planResult) { foreach ($e in @($planResult.errors)) { Write-Log "  $e" 'ERROR' } }
        exit 2
    }
    $plan = @($planResult.plan)
    Write-Log "manifest OK: $($plan.Count) enabled server(s)"

    if ($StopExisting) {
        $state = Read-State
        foreach ($key in @($state.Keys)) {
            Stop-HostPid -ProcessId ([int]$state[$key].pid) -Why 'StopExisting'
        }
        Invoke-Reap -TrackedPids @()
        if (Test-Path $StateFile) { Remove-Item $StateFile -Force }
        Write-Log 'stopped supervisor-owned hosts'
        exit 0
    }

    $state = Read-State
    $backoff = $BackoffMin


    do {
        try {
            $state = Invoke-EnsurePass -Plan $plan -State $state
            Save-State -State $state
            $backoff = $BackoffMin
        } catch {
            Write-Log "ensure-pass failed: $_" 'ERROR'
            $backoff = [math]::Min($backoff * 2, $BackoffMax)
        }
        if (-not $Once) { Start-Sleep -Seconds $HealthPollSec }
    } while (-not $Once)
}
finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
