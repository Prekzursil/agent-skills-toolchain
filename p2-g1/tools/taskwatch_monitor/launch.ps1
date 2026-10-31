# launch.ps1 — start the taskwatch live watch dashboard (rich TUI).
#
# Usage:
#   .\launch.ps1                                   # watch taskwatch.toml, new console
#   .\launch.ps1 -Inline                           # run in the current console
#   .\launch.ps1 -Registry runs\a2d.toml           # watch a specific registry
#   .\launch.ps1 -Registry runs\a2d.toml -Inline
#   .\launch.ps1 -PassThru status --json           # run any subcommand instead
#
# Mirrors tools\mcp-manager\launch.ps1 (the proven template): same $ScriptDir +
# -Inline + uv-run pattern. The CLI uses relative imports, so it is always run as
# a module (python -m cli.app), never as a bare script path.

param(
    [switch]$Inline,
    [string]$Registry = "taskwatch.toml",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PassThru
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

# Default action is the live watch dashboard; -PassThru replaces the argument
# list with any explicit subcommand (e.g. `status --json`, `list`).
if ($PassThru -and $PassThru.Count -gt 0) {
    $TwArgs = $PassThru
    $What   = "taskwatch " + ($PassThru -join " ")
} else {
    $TwArgs = @("status", "--watch", "--registry", $Registry)
    $What   = "watch dashboard ($Registry)"
}

if ($Inline) {
    Write-Host "Starting taskwatch $What (inline)..."
    Set-Location $ScriptDir
    & $UvExe run python -m cli.app @TwArgs
} else {
    Write-Host "Launching taskwatch $What..."
    $ArgLine = ($TwArgs | ForEach-Object { "'$_'" }) -join ", "
    $Command = "& '$UvExe' run python -m cli.app @($ArgLine)"
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "Set-Location '$ScriptDir'; $Command"
    )
}
