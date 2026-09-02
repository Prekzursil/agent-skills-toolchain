<#
.SYNOPSIS
    Wraps a long-running command with heartbeat progress lines and a terminal SUCCESS/FAILED marker.

.DESCRIPTION
    Launches the given command with async stdout/stderr capture, and emits a one-line
    heartbeat every -HeartbeatSec seconds showing elapsed time and the last non-empty
    log line. Ends with a terminal marker:
        SUCCESS:<id> (<elapsed>s)
        FAILED:<id> exit=<code> :: <last error line>

    Designed to be launched via run_in_background / Monitor so heartbeats stream
    as notifications. Raw output goes to log files only — the notification stream
    stays clean (one line per interval).

    INVOCATION: pass the executable via -Cmd, and all its arguments positionally
    after -Cmd <value>. PowerShell's ValueFromRemainingArguments captures every
    token (including dashed ones like -NoProfile) that follows -Cmd's value,
    without confusing them with longrun.ps1's own named parameters.

.PARAMETER Cmd
    The executable or script to run. Required.

.PARAMETER Id
    Short label for this operation. Defaults to the Cmd basename.

.PARAMETER HeartbeatSec
    Seconds between heartbeat lines. Default: 15.

.PARAMETER HangTimeoutSec
    If > 0, kills the process (entire tree) and emits FAILED if no new output
    has appeared for this many seconds. Default: 0 (disabled).

.PARAMETER LogDir
    Directory to write the log files. Default: $env:TEMP.

.PARAMETER CmdArgs
    All arguments for -Cmd. Pass positionally after the -Cmd value; they are
    captured via ValueFromRemainingArguments so dashed args are safe.

.EXAMPLE
    # Via pwsh -File (flat string / run_in_background):
    pwsh -File longrun.ps1 -Id dotnet-test -HeartbeatSec 10 -Cmd dotnet test --no-build

.EXAMPLE
    # Wrapped command with dashed flags (common case):
    pwsh -File longrun.ps1 -Id jest -HeartbeatSec 15 -HangTimeoutSec 120 -Cmd npx jest --coverage

.EXAMPLE
    # Incremental loop test (5 steps x 2s = ~10s), heartbeat every 3s:
    pwsh -File longrun.ps1 -Id loop-test -HeartbeatSec 3 -Cmd pwsh -NoProfile -Command "1..5|%{Write-Host 'step $_';Start-Sleep 2}"
#>
# PositionalBinding=$false: longrun's own options are NAMED-ONLY, so the wrapped
# command's positional args (e.g. `/c`, `-n 4`) can never leak into Id/HeartbeatSec/
# HangTimeoutSec — they are captured solely by $CmdArgs (ValueFromRemainingArguments).
[CmdletBinding(PositionalBinding=$false)]
param(
    [string]$Id            = '',
    [int]$HeartbeatSec     = 15,
    [int]$HangTimeoutSec   = 0,
    [string]$LogDir        = '',
    [string]$Cmd           = '',
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$CmdArgs     = @()
)

$ErrorActionPreference = 'Stop'

# ── Validate that a command was provided ─────────────────────────────────────
if (-not $Cmd) {
    Write-Host "FAILED:${Id} exit=1 :: Usage: longrun.ps1 [-Id <id>] [-HeartbeatSec <n>] [-HangTimeoutSec <n>] [-LogDir <dir>] -Cmd <executable> [args...]"
    exit 1
}

# ── Resolve Id ───────────────────────────────────────────────────────────────
if (-not $Id) {
    $Id = [System.IO.Path]::GetFileNameWithoutExtension($Cmd)
}

# ── Resolve log directory ─────────────────────────────────────────────────────
if (-not $LogDir) {
    $LogDir = if ($env:TEMP) { $env:TEMP } elseif ($env:TMP) { $env:TMP } else { [System.IO.Path]::GetTempPath() }
}
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# Hang window is owned by tools/plugin/heartbeat.py (monotonic hang_timeout_sec).
$HeartbeatPy = Join-Path $PSScriptRoot '..\tools\plugin\heartbeat.py'
$stamp    = '{0}-{1}' -f $PID, ([System.Diagnostics.Stopwatch]::GetTimestamp())
$logOut   = Join-Path $LogDir "longrun-${Id}-${stamp}-stdout.log"
$logErr   = Join-Path $LogDir "longrun-${Id}-${stamp}-stderr.log"
$logMerge = Join-Path $LogDir "longrun-${Id}-${stamp}-merged.log"

# Print stable log paths BEFORE launch (known even if launch fails)
Write-Host "longrun[${Id}] starting: $Cmd $($CmdArgs -join ' ')"
Write-Host "stdout log : $logOut"
Write-Host "stderr log : $logErr"
Write-Host "merged log : $logMerge"

# ── Shared state (hashtable — accessible from Register-ObjectEvent actions) ───
$startTime = [System.Diagnostics.Stopwatch]::StartNew()
$state = @{
    LastOutLine  = ''
    LastErrLine  = ''
    LastWriteMono = 0.0
    Sw = $startTime
}

# ── Build ProcessStartInfo ────────────────────────────────────────────────────
$psi = [System.Diagnostics.ProcessStartInfo]::new()
$psi.FileName               = $Cmd
$psi.UseShellExecute        = $false
$psi.CreateNoWindow         = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError  = $true

foreach ($arg in $CmdArgs) {
    $psi.ArgumentList.Add($arg)
}

$proc = [System.Diagnostics.Process]::new()
$proc.StartInfo           = $psi
$proc.EnableRaisingEvents = $true

# ── Register async event handlers ────────────────────────────────────────────
# Register-ObjectEvent is the correct PowerShell idiom for .NET events.
# -MessageData bundles log paths + state into the handler's scope.

$outData = @{ LogOut = $logOut; LogMerge = $logMerge; State = $state }
$errData = @{ LogErr = $logErr; LogMerge = $logMerge; State = $state }

$subOut = Register-ObjectEvent -InputObject $proc -EventName OutputDataReceived `
    -MessageData $outData `
    -Action {
        $line = $Event.SourceEventArgs.Data
        if ($null -ne $line) {
            try { Add-Content -LiteralPath $Event.MessageData.LogOut   -Value $line         -Encoding UTF8 -ErrorAction SilentlyContinue } catch {}
            try { Add-Content -LiteralPath $Event.MessageData.LogMerge -Value "[OUT] $line" -Encoding UTF8 -ErrorAction SilentlyContinue } catch {}
            if ($line.Trim() -ne '') {
                $Event.MessageData.State['LastOutLine']  = $line.Trim()
                $Event.MessageData.State['LastWriteMono'] = $Event.MessageData.State['Sw'].Elapsed.TotalSeconds
            }
        }
    }

$subErr = Register-ObjectEvent -InputObject $proc -EventName ErrorDataReceived `
    -MessageData $errData `
    -Action {
        $line = $Event.SourceEventArgs.Data
        if ($null -ne $line) {
            try { Add-Content -LiteralPath $Event.MessageData.LogErr   -Value $line         -Encoding UTF8 -ErrorAction SilentlyContinue } catch {}
            try { Add-Content -LiteralPath $Event.MessageData.LogMerge -Value "[ERR] $line" -Encoding UTF8 -ErrorAction SilentlyContinue } catch {}
            if ($line.Trim() -ne '') {
                $Event.MessageData.State['LastErrLine']  = $line.Trim()
                $Event.MessageData.State['LastWriteMono'] = $Event.MessageData.State['Sw'].Elapsed.TotalSeconds
            }
        }
    }

# ── Launch ────────────────────────────────────────────────────────────────────
try {
    $proc.Start() | Out-Null
    $proc.BeginOutputReadLine()
    $proc.BeginErrorReadLine()
} catch {
    Unregister-Event -SourceIdentifier $subOut.Name -ErrorAction SilentlyContinue
    Unregister-Event -SourceIdentifier $subErr.Name -ErrorAction SilentlyContinue
    Write-Host "FAILED:${Id} exit=1 :: $($_.Exception.Message)"
    exit 1
}

# ── Heartbeat + hang-detection loop ──────────────────────────────────────────
$nextHeartbeatAt = $HeartbeatSec

while (-not $proc.HasExited) {
    Start-Sleep -Milliseconds 250

    $elapsed = [int]$startTime.Elapsed.TotalSeconds

    # ── Hang detection (delegates policy to tools/plugin/heartbeat.py) ────────
    if ($HangTimeoutSec -gt 0) {
        $silentFor = $startTime.Elapsed.TotalSeconds - [double]$state['LastWriteMono']
        if ($silentFor -ge $HangTimeoutSec) {
            $lastLine = if ($state['LastErrLine']) { $state['LastErrLine'] }
                        elseif ($state['LastOutLine']) { $state['LastOutLine'] }
                        else { '(no output captured)' }
            try { & taskkill /T /F /PID $proc.Id 2>$null | Out-Null } catch { }
            try { $proc.Kill() } catch { }
            Unregister-Event -SourceIdentifier $subOut.Name -ErrorAction SilentlyContinue
            Unregister-Event -SourceIdentifier $subErr.Name -ErrorAction SilentlyContinue
            Write-Host "FAILED:${Id} exit=HANG :: hung for ${HangTimeoutSec}s with no output | last: $lastLine"
            exit 124
        }
    }

    # ── Heartbeat ─────────────────────────────────────────────────────────────
    if ($elapsed -ge $nextHeartbeatAt) {
        $lastLine = if ($state['LastErrLine'])  { $state['LastErrLine'] }
                    elseif ($state['LastOutLine']) { $state['LastOutLine'] }
                    else { '(no output yet)' }
        Write-Host "HEARTBEAT ${Id}: ${elapsed}s | $lastLine"
        $nextHeartbeatAt = $elapsed + $HeartbeatSec
    }
}

# ── Flush async handlers, collect exit code ───────────────────────────────────
$proc.WaitForExit()
$exitCode = $proc.ExitCode
$elapsed  = [int]$startTime.Elapsed.TotalSeconds

Unregister-Event -SourceIdentifier $subOut.Name -ErrorAction SilentlyContinue
Unregister-Event -SourceIdentifier $subErr.Name -ErrorAction SilentlyContinue
$proc.Dispose()

# ── Terminal marker ───────────────────────────────────────────────────────────
if ($exitCode -eq 0) {
    Write-Host "SUCCESS:${Id} (${elapsed}s)"
} else {
    $lastLine = if ($state['LastErrLine'])  { $state['LastErrLine'] }
                elseif ($state['LastOutLine']) { $state['LastOutLine'] }
                else { '(no output captured)' }
    Write-Host "FAILED:${Id} exit=$exitCode :: $lastLine"
}

exit $exitCode
