<#
.SYNOPSIS
completion.ps1 -- the PowerShell half of C1, the ONE shared completion predicate.

.DESCRIPTION
This is a PORT of hooks/_shared/completion.py, not an independent implementation. The two are held
identical by test_completion_conformance.py, which runs ONE case table against BOTH. That harness
exists because the Python and PowerShell predicates had already drifted apart in two ways:

  1. run-wave1.ps1's Test-UnitComplete required `exit == 0`; the Python side did not. F036 exited
     NON-ZERO after writing a complete 24 KB artifact and was scored FAILED. Real work, discarded.
  2. The tail scan measured DIFFERENT THINGS: `Get-Content -Tail 6` reads the last six LINES while
     Python reads the last 600 BYTES. An artifact whose sentinel is followed by seven blank lines
     passes the Python gate and fails the PowerShell one. Never observed in the wild -- which is
     precisely the point, it was waiting. This port matches Python: last 600 BYTES.

Duplication here is FORCED by the runtime boundary (PowerShell wave-runners cannot import a Python
module), so the defence is not "delete the copy" but "make the copy provably identical".

.EXAMPLE
    . "$PSScriptRoot/completion.ps1"
    $v = Get-CompletionVerdict -Artifact $u.artifact -Sentinel 'UNIT-COMPLETE' -ExitCode $rc
    if ($v.State -eq 'DONE') { ... }
#>

Set-StrictMode -Version Latest

$script:DEFAULT_MIN_BYTES = 1024
$script:DEFAULT_SENTINEL_TAIL = 600

function Test-ArtifactGate {
    <#  Exists AND >= MinBytes AND (optionally) the sentinel appears in the last N BYTES.
        Returns @{ Ok = <bool>; Why = <string> }. A read error yields Why starting with
        'DETECTOR-ERROR:' so the caller can turn it into UNKNOWN rather than a false absence. #>
    param(
        [string]$Artifact,
        [string]$Sentinel,
        [int]$MinBytes = $script:DEFAULT_MIN_BYTES,
        [int]$SentinelTail = $script:DEFAULT_SENTINEL_TAIL
    )
    if ([string]::IsNullOrEmpty($Artifact)) {
        return @{ Ok = $false; Why = 'no artifact path given' }
    }
    try {
        if (-not (Test-Path -LiteralPath $Artifact -PathType Leaf)) {
            return @{ Ok = $false; Why = 'artifact missing' }
        }
        $len = (Get-Item -LiteralPath $Artifact).Length
        if ($len -lt $MinBytes) {
            return @{ Ok = $false; Why = "artifact too small (${len}B < ${MinBytes}B)" }
        }
        if (-not [string]::IsNullOrEmpty($Sentinel)) {
            # Read the last SentinelTail BYTES -- matching Python's read()[-600:], NOT -Tail <lines>.
            $fs = [System.IO.File]::Open($Artifact, [System.IO.FileMode]::Open,
                                         [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
            try {
                $count = [Math]::Min([long]$SentinelTail, $fs.Length)
                $null = $fs.Seek(-$count, [System.IO.SeekOrigin]::End)
                $buf = New-Object byte[] $count
                $read = $fs.Read($buf, 0, $count)
                $tail = [System.Text.Encoding]::UTF8.GetString($buf, 0, $read)
            } finally { $fs.Dispose() }
            if ($tail -notlike "*$Sentinel*") {
                return @{ Ok = $false; Why = "sentinel '$Sentinel' absent from last ${SentinelTail}B" }
            }
        }
        return @{ Ok = $true; Why = "artifact ok (${len}B)" }
    } catch {
        return @{ Ok = $false; Why = "DETECTOR-ERROR: $($_.Exception.Message)" }
    }
}

function Get-CompletionVerdict {
    <#  DONE | FAILED | RUNNING | UNKNOWN. Precedence identical to completion.py:classify --
        see that module's docstring for the incident behind each rule. Nullable numerics are
        [object] so $null means "not measured" (distinct from 0, which means "measured as zero" --
        conflating those is how a blocked-but-alive process reads as dead). #>
    param(
        [string]$Artifact,
        [string]$Sentinel,
        [int]$MinBytes = $script:DEFAULT_MIN_BYTES,
        [object]$ExitCode   = $null,
        [object]$PidAlive   = $null,
        [object]$CpuDeltaS  = $null,
        [object]$CpuTotalS  = $null,   # accepted, NEVER used for liveness
        [object]$IdleS      = $null,
        [object]$StaleAfterS = $null,
        [bool]$DetectorOk   = $true
    )

    # rule 3: the detector's own health outranks everything it reports.
    if (-not $DetectorOk) {
        return @{ State = 'UNKNOWN'; Reason = 'detector reported failure; absence is not evidence' }
    }

    # rules 1+2: the artifact is the strongest single signal, and it outranks a non-zero exit.
    $gate = Test-ArtifactGate -Artifact $Artifact -Sentinel $Sentinel -MinBytes $MinBytes
    if ($gate.Ok) {
        if ($null -ne $ExitCode -and [int]$ExitCode -ne 0) {
            return @{ State = 'DONE'; Reason = "artifact valid despite exit=$ExitCode" }
        }
        return @{ State = 'DONE'; Reason = $gate.Why }
    }
    if ($gate.Why.StartsWith('DETECTOR-ERROR')) {
        return @{ State = 'UNKNOWN'; Reason = $gate.Why }
    }

    # rule 2: exit 0 with no artifact is a severed stream, not a success.
    if ($null -ne $ExitCode -and [int]$ExitCode -eq 0 -and -not [string]::IsNullOrEmpty($Artifact)) {
        return @{ State = 'FAILED'; Reason = 'severed-stream: exit 0 but artifact did not pass the gate' }
    }

    # rules 4+5: liveness by DELTA, bounded by staleness.
    if ($null -ne $PidAlive -and [bool]$PidAlive) {
        $moving = ($null -ne $CpuDeltaS) -and ([double]$CpuDeltaS -gt 0.05)
        if ($moving) {
            return @{ State = 'RUNNING'; Reason = "process alive, cpu delta ${CpuDeltaS}s" }
        }
        if ($null -ne $StaleAfterS -and $null -ne $IdleS -and [double]$IdleS -ge [double]$StaleAfterS) {
            return @{ State = 'FAILED'; Reason = "husk: alive but cpu-flat for ${IdleS}s (>= ${StaleAfterS}s)" }
        }
        if ($null -eq $CpuDeltaS) {
            return @{ State = 'UNKNOWN'; Reason = 'process alive but no cpu-delta measured' }
        }
        return @{ State = 'RUNNING'; Reason = 'process alive, cpu-flat but inside the staleness window' }
    }

    if ($null -ne $PidAlive -and -not [bool]$PidAlive) {
        return @{ State = 'FAILED'; Reason = 'process gone and no valid artifact' }
    }

    if ($null -ne $ExitCode -and [int]$ExitCode -ne 0) {
        return @{ State = 'FAILED'; Reason = "exit=$ExitCode and no valid artifact" }
    }

    return @{ State = 'UNKNOWN'; Reason = 'insufficient signals to reach a terminal verdict' }
}

function Test-UnitComplete {
    <#  Back-compat shim for the wave runners. NOTE THE BEHAVIOUR CHANGE: it no longer consults an
        exit code at all, because the old version's exit==0 requirement is the F036 bug. #>
    param([string]$Artifact, [string]$Sentinel = 'UNIT-COMPLETE')
    return (Get-CompletionVerdict -Artifact $Artifact -Sentinel $Sentinel).State -eq 'DONE'
}

# ---- conformance entry point ------------------------------------------------------------------
# Invoked as a SCRIPT (not dot-sourced) as: pwsh -File completion.ps1 -CasesFile <path>
# where the file holds a JSON ARRAY of cases. Emits one verdict state per line, in order.
# A file (not an argv blob) because a 16-case JSON payload on the command line is exactly the
# Windows 32,767-char arg-limit trap that killed two Codex runs -- prompt-by-file, always.
if ($MyInvocation.InvocationName -ne '.' -and $args.Count -ge 2 -and $args[0] -eq '-CasesFile') {
    $cases = Get-Content -LiteralPath $args[1] -Raw | ConvertFrom-Json
    foreach ($c in @($cases)) {
        $p = @{ DetectorOk = $true }
        foreach ($k in 'Artifact','Sentinel','MinBytes','ExitCode','PidAlive','CpuDeltaS','CpuTotalS','IdleS','StaleAfterS','DetectorOk') {
            if ($c.PSObject.Properties.Name -contains $k -and $null -ne $c.$k) { $p[$k] = $c.$k }
        }
        (Get-CompletionVerdict @p).State
    }
}
