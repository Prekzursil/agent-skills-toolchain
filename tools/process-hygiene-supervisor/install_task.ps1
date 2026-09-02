#requires -Version 5.1
<#
.SYNOPSIS
    Register (or remove) the ProcessHygiene scheduled task.

.DESCRIPTION
    Mirrors the Resource-Guard / MCPHostSupervisor registration pattern: a per-user
    task under a LIMITED principal that runs process-hygiene.ps1 every 5 minutes
    plus at logon, restarts on failure, and survives reboot.

    SAFE BY DEFAULT. Without -Apply the task runs the supervisor in REPORT-ONLY
    mode: it writes the JSONL ledger with result=dry-run and kills nothing, so the
    owner can review a dry-run week first. Add -Apply only after that review to
    let it stop processes. Re-run with -Apply to flip an existing task;
    an existing registration is backed up to a timestamped .xml first.

    Deploy the tested Python next to this script (hygiene.py, hygiene_actuate.py)
    and copy policy.example.json -> <Root>\policy.json before enabling -Apply.

.PARAMETER Apply       Register the task in ENFORCING mode (default: report-only).
.PARAMETER Uninstall   Remove the task.
.PARAMETER IntervalMinutes  Sampling cadence. Default 5.
.PARAMETER DigestFile  BACKGROUND-DIGEST.md the supervisor appends its anti-spam line to.
                       Default is the estate queue hooks/background-digest/reader.py reads
                       (~\.claude\BACKGROUND-DIGEST.md, same as resource-guard.ps1).
.PARAMETER OnResourceExhaustion  Also fire on Microsoft-Windows-Resource-Exhaustion-Detector
                       event 2004 (RADAR: commit charge exhausted) via a CIM event trigger.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [switch]$Apply,
    [switch]$Uninstall,
    [string]$TaskName = 'ProcessHygiene',
    [string]$Python = 'C:\Python314\python.exe',
    [string]$Root = 'C:\Users\Prekzursil\.agent-guard\process-hygiene',
    [int]$IntervalMinutes = 5,
    [string]$DigestFile = 'C:\Users\Prekzursil\.claude\BACKGROUND-DIGEST.md',
    [switch]$OnResourceExhaustion
)

$ErrorActionPreference = 'Stop'
$Script = Join-Path $PSScriptRoot 'process-hygiene.ps1'

function Write-Info { param([string]$Message) Write-Host "[install_task] $Message" }

if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        if ($PSCmdlet.ShouldProcess($TaskName, 'unregister scheduled task')) {
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
            Write-Info "removed task '$TaskName'"
        }
    }
    else {
        Write-Info "task '$TaskName' is not registered; nothing to do"
    }
    return
}

if (-not (Test-Path -LiteralPath $Script)) { throw "process-hygiene.ps1 not found: $Script" }
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'hygiene.py'))) {
    throw 'hygiene.py must sit next to install_task.ps1 (deploy the tested Python first)'
}

$policy = Join-Path $Root 'policy.json'
if (-not (Test-Path -LiteralPath $policy)) {
    Write-Warning "policy not found at $policy - copy policy.example.json there and edit the protected lists before enabling -Apply."
}
else {
    $validation = & $Python (Join-Path $PSScriptRoot 'hygiene.py') validate-policy --policy $policy 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { Write-Warning "policy.json is INVALID:`n$validation" }
    else { Write-Info "policy validates: $($validation.Trim())" }
}

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    $backup = Join-Path $Root ("{0}.BEFORE-{1}.xml" -f $TaskName, (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Force -Path $Root | Out-Null
    Export-ScheduledTask -TaskName $TaskName | Set-Content -LiteralPath $backup -Encoding utf8
    Write-Info "backed up existing task to $backup"
}

$argument = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $Script
if ($Apply) { $argument += ' -Apply' }
if ($DigestFile) { $argument += (' -DigestFile "{0}"' -f $DigestFile) }
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argument -WorkingDirectory $PSScriptRoot

$atLogon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$recurring = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration ([TimeSpan]::MaxValue)
$triggers = @($atLogon, $recurring)

if ($OnResourceExhaustion) {
    # Event-driven leg (borrowed from the commercial memory tools' teardown): the
    # Resource Exhaustion Detector logs event 2004 the moment commit charge runs
    # out - the exact instant a 5-minute cadence is too slow. Registered through
    # the CIM class because New-ScheduledTaskTrigger has no -OnEvent parameter.
    try {
        $eventClass = Get-CimClass -Namespace 'ROOT\Microsoft\Windows\TaskScheduler' -ClassName 'MSFT_TaskEventTrigger'
        $onEvent = New-CimInstance -CimClass $eventClass -ClientOnly
        $onEvent.Enabled = $true
        $onEvent.Subscription = @'
<QueryList><Query Id="0" Path="System"><Select Path="System">*[System[Provider[@Name='Microsoft-Windows-Resource-Exhaustion-Detector'] and EventID=2004]]</Select></Query></QueryList>
'@
        $triggers += $onEvent
        Write-Info 'added event trigger: Resource-Exhaustion-Detector 2004'
    }
    catch {
        Write-Warning "could not build the event trigger; continuing with time triggers only: $($_.Exception.Message)"
    }
}

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -RestartInterval (New-TimeSpan -Minutes 1) -RestartCount 3 `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if ($PSCmdlet.ShouldProcess($TaskName, "register scheduled task (apply=$($Apply.IsPresent))")) {
    Register-ScheduledTask -TaskName $TaskName -Action $action `
        -Trigger $triggers -Settings $settings -Principal $principal -Force | Out-Null
    $mode = if ($Apply) { 'ENFORCING (-Apply)' } else { 'REPORT-ONLY' }
    Write-Info "registered '$TaskName' every $IntervalMinutes min + at logon, mode=$mode"
    Write-Info "start now:  Start-ScheduledTask -TaskName $TaskName"
    Write-Info "remove:     ./install_task.ps1 -Uninstall"
}
