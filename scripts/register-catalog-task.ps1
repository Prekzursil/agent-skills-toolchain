<#
.SYNOPSIS
  Register (or remove) the daily Scheduled Task that runs the catalog sync (D12 / WU-12).

.DESCRIPTION
  One task, AgentsCatalogSync-Daily, fires daily at 03:30 and launches THIS script with -Run
  from the executed checkout. The -Run entry point is the whole runtime contract:

    1. take the Global\AgentsCatalogSync mutex; if another run holds it, log SKIP and exit 0
       (the task itself is also -MultipleInstances IgnoreNew, so this is the second fence);
    2. read Get-Counter '\Memory\Available MBytes'; below -MinFreeMB (2048) log SKIP, exit 0;
    3. run  <Python> <Toolchain>\command-center\ssot\catalog_sync.py --root <StateRoot>
       and exit with its exit code; stdout/stderr land in <StateRoot>\last-run.*.txt and one
       line per run is appended to <StateRoot>\task-runs.log.

  Task settings: -MultipleInstances IgnoreNew, -ExecutionTimeLimit (New-TimeSpan -Minutes 20),
  -StartWhenAvailable (a missed 03:30 runs at the next opportunity), interactive principal at
  LIMITED run level. Nothing here needs or stores a credential: every feed catalog_sync.py
  reads is anonymous.

  -DryRun prints the exact registration (trigger, settings, action, guards, preflight) and
  registers NOTHING; it touches no ScheduledTasks cmdlet, so it also runs on Linux pwsh for
  the text-contract test. -Unregister removes the task; absent is not an error.

  The action always names the EXECUTED checkout (-Toolchain, default
  C:\Users\Prekzursil\source\agent-skills-toolchain), never the checkout this file happens to
  be run from: CLAUDE.md's SSOT-WIRE rule forbids a task that references a scratch clone.

.PARAMETER DryRun       Print the registration and register nothing.
.PARAMETER Unregister   Remove AgentsCatalogSync-Daily.
.PARAMETER Run          Task entry point: guards, then catalog_sync.py (do not call by hand
                        except to test; combine with -DryRun to see the command only).
.PARAMETER Python       Interpreter for catalog_sync.py.
.PARAMETER Toolchain    The executed checkout; catalog_sync.py and this script are resolved under it.
.PARAMETER StateRoot    catalog_sync.py --root (cache, index, diff, run log).
.PARAMETER At           Daily trigger time, HH:mm.
.PARAMETER MinFreeMB    Skip the run when available RAM is below this many MB.

.EXAMPLE
  .\register-catalog-task.ps1 -DryRun
  .\register-catalog-task.ps1
  .\register-catalog-task.ps1 -Run -DryRun
  .\register-catalog-task.ps1 -Unregister
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Unregister,
    [switch]$Run,
    [string]$Python = 'C:\Python314\python.exe',
    [string]$Toolchain = 'C:\Users\Prekzursil\source\agent-skills-toolchain',
    [string]$StateRoot = 'C:\Users\Prekzursil\.agents\state\catalog',
    [ValidatePattern('^\d{2}:\d{2}$')]
    [string]$At = '03:30',
    [int]$MinFreeMB = 2048
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$TaskName    = 'AgentsCatalogSync-Daily'
$MutexName   = 'Global\AgentsCatalogSync'
$TimeLimit   = New-TimeSpan -Minutes 20
$SyncScript  = Join-Path $Toolchain 'command-center\ssot\catalog_sync.py'
$TaskScript  = Join-Path $Toolchain 'scripts\register-catalog-task.ps1'
$RunLog      = Join-Path $StateRoot 'task-runs.log'
$Description = 'Daily catalog sync (D12): refreshes the upstream model catalogs under ' +
               "$StateRoot and writes the standing diff. Report-only; retirement is a human write-back."

function Write-Info { param([string]$Message) Write-Host "[catalog-task] $Message" }

function Write-RunLog {
    param([string]$Line)
    $stamp = Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK'
    Write-Host "$stamp $Line"
    if (Test-Path -LiteralPath $StateRoot) {
        Add-Content -LiteralPath $RunLog -Value "$stamp $Line" -Encoding utf8
    }
}

function Get-AvailableMB {
    # The spec'd counter first; its path is localised on non-English Windows, so a failure
    # falls back to CIM rather than skipping every run forever.
    try {
        $sample = Get-Counter '\Memory\Available MBytes' -ErrorAction Stop
        return [int][math]::Floor($sample.CounterSamples[0].CookedValue)
    } catch {
        try {
            $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
            return [int][math]::Floor($os.FreePhysicalMemory / 1024)
        } catch {
            # Neither cmdlet exists off Windows; this keeps `-Run -DryRun` testable there.
            return [int][math]::Floor([System.GC]::GetGCMemoryInfo().TotalAvailableMemoryBytes / 1MB)
        }
    }
}

function Resolve-Shell {
    $pwsh = Get-Command pwsh.exe -ErrorAction SilentlyContinue
    if ($pwsh) { return $pwsh.Source }
    return (Get-Command powershell.exe).Source
}

$ActionArgument = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Run -Python "{1}" -Toolchain "{2}" -StateRoot "{3}" -MinFreeMB {4}' -f `
    $TaskScript, $Python, $Toolchain, $StateRoot, $MinFreeMB

# ------------------------------------------------------------------------ -Run
if ($Run) {
    if (-not (Test-Path -LiteralPath $StateRoot)) {
        New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null
    }
    $mutex = New-Object System.Threading.Mutex($false, $MutexName)
    $held = $false
    try {
        try {
            $held = $mutex.WaitOne(0)
        } catch [System.Threading.AbandonedMutexException] {
            # A previous run was killed (ExecutionTimeLimit) while holding it; ownership
            # still transfers to us, so the run proceeds.
            $held = $true
            Write-RunLog "NOTE:catalog-sync $MutexName was abandoned by a killed run"
        }
        if (-not $held) {
            Write-RunLog "SKIP:catalog-sync another run holds $MutexName"
            exit 0
        }
        $freeMB = Get-AvailableMB
        if ($freeMB -lt $MinFreeMB) {
            Write-RunLog "SKIP:catalog-sync available RAM $freeMB MB < $MinFreeMB MB"
            exit 0
        }
        $commandLine = '"{0}" "{1}" --root "{2}"' -f $Python, $SyncScript, $StateRoot
        if ($DryRun) {
            Write-RunLog "DRYRUN:catalog-sync would run $commandLine (available RAM $freeMB MB)"
            exit 0
        }
        foreach ($required in @($Python, $SyncScript)) {
            if (-not (Test-Path -LiteralPath $required)) {
                Write-RunLog "FAILED:catalog-sync missing $required"
                exit 2
            }
        }
        $stdout = Join-Path $StateRoot 'last-run.stdout.txt'
        $stderr = Join-Path $StateRoot 'last-run.stderr.txt'
        $proc = Start-Process -FilePath $Python `
            -ArgumentList ('"{0}" --root "{1}"' -f $SyncScript, $StateRoot) `
            -WorkingDirectory $StateRoot -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        $summary = ''
        if (Test-Path -LiteralPath $stdout) {
            $summary = (Get-Content -LiteralPath $stdout -Tail 1 -ErrorAction SilentlyContinue) -join ' '
        }
        Write-RunLog "EXIT:catalog-sync $($proc.ExitCode) (available RAM $freeMB MB) $summary"
        exit $proc.ExitCode
    } finally {
        if ($held) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}

# ----------------------------------------------------------------- -Unregister
if ($Unregister) {
    if ($DryRun) {
        Write-Info "DRY RUN - would run: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
        return
    }
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $existing) {
        Write-Info "task '$TaskName' is not registered; nothing to do"
        return
    }
    try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch {}
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Info "removed task '$TaskName'"
    return
}

# -------------------------------------------------------------------- register
$preflight = [ordered]@{
    'python'          = Test-Path -LiteralPath $Python
    'catalog_sync.py' = Test-Path -LiteralPath $SyncScript
    'task script'     = Test-Path -LiteralPath $TaskScript
    'state root'      = Test-Path -LiteralPath $StateRoot
}
$principalText = "$env:USERDOMAIN\$env:USERNAME (Interactive, RunLevel Limited)"
$settingsText  = '-MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20) ' +
                 '-StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries'
$shellText     = if ($DryRun) { 'pwsh.exe (or powershell.exe when pwsh is absent)' } else { Resolve-Shell }
$guardsText    = "mutex $MutexName held for the run (skip if another run holds it); " +
                 "skip when Get-Counter '\Memory\Available MBytes' < $MinFreeMB"

$plan = @(
    "TaskName      : $TaskName",
    "Trigger       : Daily at $At",
    "Settings      : $settingsText",
    "Principal     : $principalText",
    "Execute       : $shellText",
    "Argument      : $ActionArgument",
    "Guards (-Run) : $guardsText",
    "Launches      : $Python $SyncScript --root $StateRoot",
    "Run log       : $RunLog",
    "Description   : $Description"
)
foreach ($key in $preflight.Keys) {
    $plan += 'Preflight     : {0,-16} exists={1}' -f $key, $preflight[$key]
}

if ($DryRun) {
    Write-Info 'DRY RUN - nothing is registered'
    foreach ($line in $plan) { Write-Host "  $line" }
    if ($PSCommandPath -and ($PSCommandPath -ne $TaskScript)) {
        Write-Info "note: running from $PSCommandPath; the task will execute $TaskScript"
    }
    return
}

foreach ($key in @('python', 'catalog_sync.py', 'task script')) {
    if (-not $preflight[$key]) {
        throw "preflight failed: $key not found (python=$Python toolchain=$Toolchain); fix the path or pass -DryRun"
    }
}
if (-not $preflight['state root']) {
    New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null
    Write-Info "created state root $StateRoot"
}

$trigger   = New-ScheduledTaskTrigger -Daily -At $At
$settings  = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit $TimeLimit -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited
$action    = New-ScheduledTaskAction -Execute (Resolve-Shell) -Argument $ActionArgument `
    -WorkingDirectory $StateRoot

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) { Write-Info "replacing existing task '$TaskName' (state: $($existing.State))" }

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Description $Description -Force | Out-Null

Write-Info "registered '$TaskName'"
foreach ($line in $plan) { Write-Host "  $line" }
Write-Info "first live run by hand: Start-ScheduledTask -TaskName $TaskName ; then Get-Content `"$RunLog`" -Tail 3"
