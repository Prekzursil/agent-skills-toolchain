<#
.SYNOPSIS
    Start the chrome-bridge hub (no MCP stdio) on loopback.

.PARAMETER Mode
    agent (127.0.0.1:8770) or live (127.0.0.1:8790).
#>
[CmdletBinding()]
param(
    [ValidateSet('agent', 'live')]
    [string]$Mode = 'agent',

    [switch]$Stop
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$port = if ($Mode -eq 'live') { 8790 } else { 8770 }
$root = $PSScriptRoot
$entry = Join-Path $root 'chrome-bridge-mcp\dist\index.js'
$logDir = Join-Path $root 'logs'
$log = Join-Path $logDir "hub-$Mode.log"
$pidFile = Join-Path $logDir "hub-$Mode.pid"

if (-not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

function Test-HubPid {
    if (-not (Test-Path -LiteralPath $pidFile)) { return $null }
    $raw = (Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not $raw) { return $null }
    $procId = 0
    if (-not [int]::TryParse($raw.Trim(), [ref]$procId)) { return $null }
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($proc -and $proc.ProcessName -match 'node') { return $proc }
    return $null
}

if ($Stop) {
    $proc = Test-HubPid
    if ($proc) {
        Stop-Process -Id $proc.Id -Force
        Write-Output "SUCCESS:hub stopped pid=$($proc.Id) mode=$Mode"
    } else {
        Write-Output "SUCCESS:hub nothing-to-stop mode=$Mode"
    }
    if (Test-Path -LiteralPath $pidFile) { Remove-Item -LiteralPath $pidFile -Force }
    exit 0
}

if (-not (Test-Path -LiteralPath $entry)) {
    Write-Output "FAILED:hub dist missing — build chrome-bridge-mcp first ($entry)"
    exit 1
}

$existing = Test-HubPid
if ($existing) {
    Write-Output "SUCCESS:hub already pid=$($existing.Id) ws=127.0.0.1:$port"
    exit 0
}

$node = (Get-Command node -ErrorAction Stop).Source
$proc = Start-Process -FilePath $node -ArgumentList @($entry, '--hub-only', '--port', "$port") -PassThru -WindowStyle Hidden -RedirectStandardError $log -RedirectStandardOutput (Join-Path $logDir "hub-$Mode.stdout.log")
$proc.Id | Set-Content -LiteralPath $pidFile -Encoding ascii
Start-Sleep -Milliseconds 600
if ($proc.HasExited) {
    Write-Output "FAILED:hub exited immediately code=$($proc.ExitCode) log=$log"
    exit 1
}
Write-Output "SUCCESS:hub started pid=$($proc.Id) ws=127.0.0.1:$port log=$log"
exit 0
