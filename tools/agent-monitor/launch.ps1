# launch.ps1 — start the agent-monitor.
# Usage:
#   .\launch.ps1            # friendly Tkinter UI (default; this is what /agent-monitor runs)
#   .\launch.ps1 -Watch     # legacy terminal overview dashboard
#   .\launch.ps1 -Spawn     # legacy: one terminal per agent
#   .\launch.ps1 -Inline    # run the legacy mode in the current console
param(
    [switch]$Watch,
    [switch]$Spawn,
    [switch]$Inline
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# resolve interpreters: console python (legacy modes) + windowed pythonw (UI)
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
$pyw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $py -and -not $pyw) { Write-Error "Python 3 not found on PATH. Install Python 3."; exit 1 }

if ($Watch -or $Spawn) {
    $margs = if ($Spawn) { @('--spawn', '--all') } else { @('--watch') }
    $runner = if ($py) { $py } else { $pyw }
    if ($Inline) {
        & $runner "$ScriptDir\agent_monitor.py" @margs
    } else {
        $inner = "& '$runner' '$ScriptDir\agent_monitor.py' " + ($margs -join ' ')
        Start-Process powershell -ArgumentList @("-NoExit", "-NoProfile", "-Command", "Set-Location '$ScriptDir'; $inner")
    }
} else {
    # default: the Tkinter UI (windowed, no console window)
    $runner = if ($pyw) { $pyw } else { $py }
    Start-Process -FilePath $runner -ArgumentList @("$ScriptDir\agent_monitor_ui.py") -WorkingDirectory $ScriptDir
}
