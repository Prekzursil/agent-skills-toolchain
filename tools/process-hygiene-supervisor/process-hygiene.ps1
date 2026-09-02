#requires -Version 5.1
<#
.SYNOPSIS
    Thin snapshot-gatherer + launcher for the process-hygiene decision engine.

.DESCRIPTION
    This script does NO decision-making. It samples the Windows process table and
    memory/WSL/listener signals into the JSON snapshot schema that hygiene.py
    validates, then shells to `hygiene.py run`, which decides and (with -Apply)
    actuates through hygiene_actuate.WindowsActuator (a pinned process handle,
    never taskkill /F by PID). All rules, thresholds and
    the audit ledger live in Python and are unit-tested; this file only actuates
    the OS-specific data collection - the same Python-decides / PowerShell-
    gathers split that tools/mcp/mcp-host-supervisor uses.

    Fail-open: every path is wrapped so the scheduled task can only exit 0/2, and
    a sampling error degrades a signal rather than crashing the run.

    DEFAULT IS REPORT-ONLY. Pass -Apply (the install task adds it only when the
    owner opts in) to allow the engine to stop processes. Report-only writes the same
    ledger with result=dry-run so a dry-run week is auditable before any kill.

.PARAMETER Apply         Allow the engine to stop processes / terminate idle WSL distros.
.PARAMETER Python        Python interpreter. Default C:\Python314\python.exe.
.PARAMETER Root          Protected runtime root for policy/state/ledger.
.PARAMETER DigestFile    BACKGROUND-DIGEST.md to append one anti-spam line to on kills ('' = off).
.PARAMETER ProcessSnapshotFile  TEST override: use this snapshot instead of sampling.
.PARAMETER EmitSnapshotOnly     TEST: write the sampled snapshot to -SnapshotOut and exit.
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [string]$Python = 'C:\Python314\python.exe',
    [string]$ToolDir = $PSScriptRoot,
    [string]$Root = 'C:\Users\Prekzursil\.agent-guard\process-hygiene',
    [string]$PolicyFile = '',
    [string]$StateFile = '',
    [string]$LedgerFile = '',
    [string]$DigestFile = '',
    [string]$ReaperAvailable = '',
    [string]$ProcessSnapshotFile = '',
    [string]$SnapshotOut = '',
    [switch]$EmitSnapshotOnly
)

$ErrorActionPreference = 'Stop'
if (-not $PolicyFile) { $PolicyFile = Join-Path $Root 'policy.json' }
if (-not $StateFile) { $StateFile = Join-Path $Root 'state\process-hygiene.state.json' }
if (-not $LedgerFile) { $LedgerFile = Join-Path $Root 'ledger\process-hygiene.jsonl' }

function Convert-ToUnix([object]$Value) {
    if ($Value -is [datetime]) { return [DateTimeOffset]$Value | ForEach-Object { $_.ToUnixTimeSeconds() } }
    $parsed = [DateTimeOffset]::MinValue
    if ([DateTimeOffset]::TryParse([string]$Value, [ref]$parsed)) { return $parsed.ToUnixTimeSeconds() }
    return 0L
}

function Get-HygieneSnapshot {
    # Build the snapshot object matching hygiene.py's SCHEMA_SNAPSHOT.
    $cim = @(Get-CimInstance Win32_Process -ErrorAction Stop)
    $metrics = @{}
    foreach ($p in Get-Process -ErrorAction SilentlyContinue) { $metrics[[int]$p.Id] = $p }

    $processes = foreach ($process in $cim) {
        $id = [int]$process.ProcessId
        $metric = $metrics[$id]
        $io = $null
        if ($null -ne $process.ReadTransferCount -and $null -ne $process.WriteTransferCount) {
            $io = [long]$process.ReadTransferCount + [long]$process.WriteTransferCount
        }
        # CPU: prefer the WMI kernel+user times (100 ns units). They come from the
        # WMI provider, which sees EVERY process, including vmmemWSL and other
        # protected/elevated ones where Get-Process .CPU is silently $null. Without
        # this the idle detector never confirms vmmem idle and the WSL rule is dead.
        $cpu = $null
        if ($null -ne $process.KernelModeTime -and $null -ne $process.UserModeTime) {
            $cpu = ([double]$process.KernelModeTime + [double]$process.UserModeTime) / 1e7
        }
        elseif ($metric -and $null -ne $metric.CPU) { $cpu = [double]$metric.CPU }
        [ordered]@{
            pid               = $id
            ppid              = [int]$process.ParentProcessId
            name              = [string]$process.Name
            executable        = [string]$process.ExecutablePath
            command_line      = [string]$process.CommandLine
            created_unix      = [long](Convert-ToUnix $process.CreationDate)
            cpu_seconds       = $cpu
            io_bytes          = $io
            working_set_bytes = if ($metric) { [long]$metric.WorkingSet64 } else { 0L }
            private_bytes     = if ($metric) { [long]$metric.PrivateMemorySize64 } else { 0L }
        }
    }

    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    $physical = [long]$os.TotalVisibleMemorySize * 1KB
    # NOTE on `free_bytes`, because the name invites a wrong "fix":
    # FreePhysicalMemory is Task Manager's AVAILABLE (free + zero + standby lists) -
    # the same quantity as the perfmon counter \Memory\Available MBytes, i.e. memory
    # immediately allocatable without writing anything to disk. It is NOT the free
    # page list (that is \Memory\Free & Zero Page List Bytes, which is near zero by
    # design on a healthy box). The policy's freeBytesBelow thresholds are calibrated
    # against AVAILABLE, so do not "correct" this to a free-page-list counter.
    $free = [long]$os.FreePhysicalMemory * 1KB
    $commitTotal = ([long]$os.TotalVirtualMemorySize - [long]$os.FreeVirtualMemory) * 1KB
    $commitLimit = [long]$os.TotalVirtualMemorySize * 1KB
    try {
        $committed = (Get-Counter '\Memory\Committed Bytes' -ErrorAction Stop).CounterSamples[0].CookedValue
        $limit = (Get-Counter '\Memory\Commit Limit' -ErrorAction Stop).CounterSamples[0].CookedValue
        if ($committed -gt 0) { $commitTotal = [long]$committed }
        if ($limit -gt 0) { $commitLimit = [long]$limit }
    } catch { }

    $compressed = $null
    $mc = Get-Process -Name 'Memory Compression' -ErrorAction SilentlyContinue
    if ($mc) { $compressed = [long]($mc | Measure-Object WorkingSet64 -Sum).Sum }

    $running = @()
    $wslAvailable = $false
    try {
        # WSL_UTF8=1 makes wsl.exe emit UTF-8 instead of UTF-16LE (the historic
        # source of the "\0"-riddled distro names); the strip below stays as a belt.
        $env:WSL_UTF8 = '1'
        $wslList = & wsl.exe --list --running --quiet 2>$null
        $wslAvailable = ($LASTEXITCODE -eq 0)
        if ($wslList) {
            $running = @($wslList | ForEach-Object { ($_ -replace '\0', '').Trim() } | Where-Object { $_ })
        }
    } catch { }
    # Gates for the idle shutdown: Docker Desktop's distros must stay up, and any
    # live wsl.exe client (VS Code Remote-WSL, an attached terminal) would lose
    # its session - both are sourced from the vscode-remote-release / Docker
    # Desktop trackers. Counted here, decided in Python.
    $dockerDesktop = [bool](Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue)
    $wslClients = @(Get-Process -Name 'wsl' -ErrorAction SilentlyContinue).Count

    $listeners = @()
    $connections = @()
    try {
        foreach ($conn in (Get-NetTCPConnection -State Listen -ErrorAction Stop)) {
            $listeners += [ordered]@{ port = [int]$conn.LocalPort; pid = [int]$conn.OwningProcess }
        }
        # ESTABLISHED sockets feed the network veto: an "idle" agent may simply be
        # waiting on a model response. Loopback is filtered in Python.
        foreach ($conn in (Get-NetTCPConnection -State Established -ErrorAction Stop)) {
            # bracket IPv6 so `addr:port` stays parseable ([::1]:8812, not ::1:8812)
            $addr = [string]$conn.RemoteAddress
            if ($addr -match ':') { $addr = "[$addr]" }
            $connections += [ordered]@{
                pid    = [int]$conn.OwningProcess
                remote = ('{0}:{1}' -f $addr, $conn.RemotePort)
            }
        }
    } catch { }

    return [ordered]@{
        schema          = 'process-hygiene-snapshot-v1'
        taken_unix      = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        host            = [ordered]@{
            physical_bytes     = $physical
            free_bytes         = $free
            commit_total_bytes = $commitTotal
            commit_limit_bytes = $commitLimit
            compressed_bytes   = $compressed
        }
        wsl             = [ordered]@{
            available              = $wslAvailable
            running_distros        = $running
            docker_desktop_running = $dockerDesktop
            client_count           = [int]$wslClients
        }
        listeners       = $listeners
        connections     = $connections
        supervisor_pids = @([int]$PID)
        processes       = @($processes)
    }
}

try {
    New-Item -ItemType Directory -Force -Path $Root, (Split-Path -Parent $StateFile), (Split-Path -Parent $LedgerFile) | Out-Null

    if ($ProcessSnapshotFile) {
        $snapshotPath = $ProcessSnapshotFile
    }
    else {
        $snapshot = Get-HygieneSnapshot
        $snapshotPath = if ($SnapshotOut) { $SnapshotOut } else { Join-Path $env:TEMP ("process-hygiene-{0}.json" -f [guid]::NewGuid().ToString('N')) }
        $snapshot | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $snapshotPath -Encoding utf8
    }

    if ($EmitSnapshotOnly) {
        Write-Output "SUCCESS:process-hygiene-snapshot-emit $snapshotPath"
        exit 0
    }

    $pyArgs = @(
        (Join-Path $ToolDir 'hygiene.py'), 'run',
        '--snapshot', $snapshotPath,
        '--policy', $PolicyFile,
        '--state', $StateFile,
        '--ledger', $LedgerFile
    )
    if ($Apply) { $pyArgs += '--apply' }
    if ($ReaperAvailable) { $pyArgs += @('--reaper-available', $ReaperAvailable) }
    if ($DigestFile) { $pyArgs += @('--digest', $DigestFile) }

    $output = & $Python @pyArgs
    $code = $LASTEXITCODE
    Write-Output ($output | Select-Object -Last 1)
    if (-not $ProcessSnapshotFile -and -not $SnapshotOut -and (Test-Path -LiteralPath $snapshotPath)) {
        Remove-Item -LiteralPath $snapshotPath -Force -ErrorAction SilentlyContinue
    }
    exit $code
}
catch {
    Write-Output "FAILED:process-hygiene launcher failed closed; no action taken; reason=$($_.Exception.Message)"
    exit 2
}
