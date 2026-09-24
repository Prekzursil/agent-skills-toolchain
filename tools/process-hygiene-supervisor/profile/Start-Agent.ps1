#requires -Version 5.1
<#
.SYNOPSIS
    Profile functions that launch agent CLIs through the process-hygiene gate + job object.

.DESCRIPTION
    Dot-source this from $PROFILE (or copy the functions in):

        . 'C:\Users\Prekzursil\.agent-guard\process-hygiene\profile\Start-Agent.ps1'

    Then `claude`, `codex`, `cursor-agent`, `grok`, `goose` keep working as commands - but
    they now run through hygiene_launch.py, which

      1. asks the supervisor's heartbeat whether the box can take another session
         (critical tier or a commit limit < 30 min away REFUSES with exit 75; elevated
         admits with a warning; the gate fails OPEN if the supervisor is down);
      2. puts the launcher, and therefore every descendant, in a Windows job object with
         KILL_ON_JOB_CLOSE, so closing this shell - or killing the launcher - tears the
         whole tree down and the orphan class cannot form;
      3. writes a per-session bill (peak job memory, duration, exit code) to
         <root>\ledger\sessions.jsonl.

    PowerShell FUNCTIONS win command precedence over executables of the same name, which
    is why this is a set of functions and NOT a PATH shim: nothing is shadowed on disk,
    `Get-Command claude -CommandType Application` still finds the real binary, and removing
    the dot-source from $PROFILE restores the plain commands with no residue.

    Per-runtime hard caps below are the queue's suggested ceilings (Q7 in the decision
    queue); they FAIL further commit inside the tree rather than killing anything, and a
    session that legitimately needs more can be launched with `Start-Agent -NoLimit ...`.

.PARAMETER NoLimit   Skip the per-runtime job memory cap for this launch.
.PARAMETER Force     Launch even when the gate refuses (recorded in the bill).
#>

$script:HygieneRoot   = if ($env:PROCESS_HYGIENE_ROOT) { $env:PROCESS_HYGIENE_ROOT } else { 'C:\Users\Prekzursil\.agent-guard\process-hygiene' }
$script:HygienePython = if ($env:PROCESS_HYGIENE_PYTHON) { $env:PROCESS_HYGIENE_PYTHON } else { 'C:\Python314\python.exe' }

# Hard commit caps per runtime, bytes. Soft (notify) is half of hard.
$script:AgentJobLimits = @{
    'claude'       = 6GB
    'codex'        = 4GB
    'cursor-agent' = 4GB
    'grok'         = 3GB
    'goose'        = 3GB
}

function Start-Agent {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Runtime,
        [switch]$NoLimit,
        [switch]$Force,
        [Parameter(ValueFromRemainingArguments)][string[]]$Arguments
    )
    $binary = Get-Command $Runtime -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $binary) { throw "Start-Agent: '$Runtime' is not an installed application" }
    $launcher = Join-Path $script:HygieneRoot 'hygiene_launch.py'
    if (-not (Test-Path -LiteralPath $launcher)) {
        Write-Warning "Start-Agent: $launcher not found; running '$Runtime' directly (no gate, no job object)"
        & $binary.Source @Arguments
        return
    }
    $pyArgs = @($launcher, '--runtime', $Runtime)
    if (-not $NoLimit -and $script:AgentJobLimits.ContainsKey($Runtime)) {
        $hard = [long]$script:AgentJobLimits[$Runtime]
        $pyArgs += @('--job-memory-limit', $hard, '--notify-limit', [long]($hard / 2))
    }
    if ($Force) { $pyArgs += '--force' }
    $pyArgs += @('--', $binary.Source) + $Arguments
    & $script:HygienePython @pyArgs
    $code = $LASTEXITCODE
    if ($code -eq 75) {
        Write-Host "Start-Agent: the box refused a new '$Runtime' session (memory). Free something first, or: Start-Agent $Runtime -Force" -ForegroundColor Yellow
    }
    $global:LASTEXITCODE = $code
}

# The plain command names, as functions (precedence over the .exe, nothing shadowed).
function claude       { Start-Agent -Runtime 'claude'       @args }
function codex        { Start-Agent -Runtime 'codex'        @args }
function cursor-agent { Start-Agent -Runtime 'cursor-agent' @args }
function grok         { Start-Agent -Runtime 'grok'         @args }
function goose        { Start-Agent -Runtime 'goose'        @args }
