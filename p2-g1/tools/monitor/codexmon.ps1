<#
.SYNOPSIS
  codexmon - single-instance launcher for the monitorcore codexmon board.

.DESCRIPTION
  The canonical entry point for /codex-monitor. It renders the monitorcore
  codex board (~/.agents/skills/workflow-monitor/codex_monitor.py) and solves
  two verified defects found on 2026-07-18:

    1. ACCUMULATION. Every bare launch spawns another python board; repeated
       /codex-monitor calls left three orphaned mingle-era monitors resident on
       a ~1GB-free box. This wrapper refuses a second live board unless -Force,
       and -Reap clears strays (current + retired mingle-era).

    2. wt/ConPTY DEATH. `mon codexmon` launches the board via
       `wt new-tab`, and the board's interactive loop exits immediately under
       wt's ConPTY (verified: renders one ~21KB frame, clean exit 0, empty
       stderr). Launched in a plain new console via Start-Process it survives.
       So this wrapper launches with Start-Process -WindowStyle Normal, NOT wt.
       (The underlying wt/ConPTY fix is a monitorcore change tracked separately;
       this wrapper is the reversible TIER-0 workaround.)

  It lives in ~/.local/bin - NOT under ~/.agents/skills - so a future
  sync-skills run cannot clobber it, and deleting this one file is a full
  rollback.

.PARAMETER Force
  Open another board even if one is already running.

.PARAMETER Reap
  Kill every codexmon board (current monitorcore + retired mingle-era) and exit.

.EXAMPLE
  codexmon.ps1                    # open the board, or report the one already up
  codexmon.ps1 --since-min 120    # passthrough flags reach the entry script
  codexmon.ps1 --once             # one frame to stdout (no window); for checks
  codexmon.ps1 -Reap              # clear strays
#>
[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$Reap,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PassThru = @()
)

Set-StrictMode -Version Latest

$Board = Join-Path $env:USERPROFILE '.agents\skills\workflow-monitor\codex_monitor.py'
if (-not (Test-Path $Board)) {
    Write-Output "codexmon: entry script not found at $Board"
    Write-Output '  deploy it from origin/main: git show origin/main:skills/workflow-monitor/codex_monitor.py'
    exit 1
}
$Py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Py) { Write-Output 'codexmon: python not on PATH'; exit 1 }

# Distinguish the current monitorcore board from the retired mingle-era one:
# a stale legacy process must NOT suppress the real board, but -Reap clears both.
# NB: use '.' (any-char) for the path separator, NOT '\c' - in .NET regex '\c' is a
# control-character escape (\cX), so 'workflow-monitor\codex...' silently never matches.
$CurrentPattern = 'workflow-monitor.codex_monitor\.py'
$LegacyPattern = 'mingle.monitor.codex_monitor\.py'

function Get-CodexBoard {
    param([string]$Pattern)
    @(Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match $Pattern })
}

$current = Get-CodexBoard -Pattern $CurrentPattern
$legacy = Get-CodexBoard -Pattern $LegacyPattern

if ($Reap) {
    $all = @($current) + @($legacy)
    if (-not $all) { Write-Output 'codexmon: no boards running - nothing to reap'; exit 0 }
    foreach ($p in $all) {
        try {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
            Write-Output "reaped pid $($p.ProcessId)"
        } catch {
            Write-Output "could not reap pid $($p.ProcessId): $($_.Exception.Message)"
        }
    }
    exit 0
}

# --once renders a single frame to stdout and exits; run it INLINE (no window,
# capturable) - it can never accumulate, so the guard does not apply.
if ($PassThru -contains '--once') {
    $env:PYTHONPATH = Join-Path $env:USERPROFILE '.agents\skills\workflow-monitor'
    & $Py $Board @PassThru
    exit $LASTEXITCODE
}

if ($current -and -not $Force) {
    Write-Output "codexmon: already running (pid $(($current.ProcessId) -join ', ')) - not spawning a duplicate."
    Write-Output '  -Force to open another  |  -Reap to clear it'
    if ($legacy) {
        Write-Output "  note: $($legacy.Count) retired mingle-era monitor(s) also resident (pid $(($legacy.ProcessId) -join ', ')) - -Reap clears those too"
    }
    exit 0
}

if ($legacy) {
    Write-Output "codexmon: $($legacy.Count) retired mingle-era monitor(s) resident (pid $(($legacy.ProcessId) -join ', ')); -Reap clears them"
}

# LAUNCH PATH - measured, not guessed (2026-07-18). Three forms were tested:
#   wt new-tab ............ board DIES (ConPTY kills the interactive loop)
#   cmd /c start .......... board DIES (verified twice: 0 processes alive 4s later)
#   Start-Process -WindowStyle Normal ... board SURVIVES (verified: alive at 8s, 21KB output)
# So: Start-Process into a plain new console. PYTHONPATH puts the vendored monitorcore
# on the path so the thin codex_monitor.py shim resolves `monitorcore.codex_tail`.
$env:PYTHONPATH = Join-Path $env:USERPROFILE '.agents\skills\workflow-monitor'
$board = Start-Process -FilePath $Py -ArgumentList (@($Board) + $PassThru) `
    -WorkingDirectory (Split-Path $Board) -WindowStyle Normal -PassThru

# Verify it is actually ALIVE before claiming success - a launcher that reports
# "launched" for a process that died 2s later is exactly the false-SUCCESS this
# workspace has a rule against (rules/common/single-signal-verification.md).
Start-Sleep -Seconds 3
if (Get-Process -Id $board.Id -ErrorAction SilentlyContinue) {
    Write-Output "codexmon: board running (pid $($board.Id)) in its own console window."
    exit 0
} else {
    Write-Output "codexmon: FAILED - the board exited within 3s of launch."
    Write-Output "  Fallback that always works: codexmon.ps1 --once   (renders one frame inline)"
    exit 1
}
