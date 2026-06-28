# launch.ps1 — start the mcp-manager TUI in a new console window.
# Usage:
#   .\launch.ps1            # opens a new console
#   .\launch.ps1 -Inline    # runs in the current console (for debugging)

param(
    [switch]$Inline,
    [switch]$Tui      # use the legacy Textual TUI (ui/app.py) instead of the PySide6 window
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$UvExe     = "C:\Users\Prekzursil\.local\bin\uv.exe"

if (-not (Test-Path $UvExe)) {
    # Fallback: find uv on PATH
    $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
    $UvExe = if ($uvCmd) { $uvCmd.Source } else { $null }
    if (-not $UvExe) {
        Write-Error "uv not found. Install with: winget install astral-sh.uv"
        exit 1
    }
}

$Entry   = if ($Tui) { "$ScriptDir\ui\app.py" } else { "$ScriptDir\ui\gui.py" }
$What    = if ($Tui) { "Textual TUI" } else { "desktop window (PySide6)" }
$Command = "`"$UvExe`" run python `"$Entry`""

if ($Inline) {
    Write-Host "Starting mcp-manager $What (inline)..."
    Set-Location $ScriptDir
    & $UvExe run python "$Entry"
} else {
    Write-Host "Launching mcp-manager $What..."
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "Set-Location '$ScriptDir'; $Command"
    )
}
