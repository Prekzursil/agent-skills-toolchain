<#
.SYNOPSIS
    Start the chrome-bridge hub (no MCP stdio) on loopback with a mandatory token.

.PARAMETER Mode
    agent (127.0.0.1:8770, extension-agent pin) or live (127.0.0.1:8790, extension-live pin).
#>
[CmdletBinding()]
param(
    [ValidateSet('agent', 'live')]
    [string]$Mode = 'agent',

    [switch]$Stop
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'lib\BridgeAuth.ps1')

$port = if ($Mode -eq 'live') { 8790 } else { 8770 }
$root = $PSScriptRoot
$entry = Join-Path $root 'chrome-bridge-mcp\dist\index.js'
$logDir = Join-Path $root 'logs'
$log = Join-Path $logDir "hub-$Mode.log"
$stdoutLog = Join-Path $logDir "hub-$Mode.stdout.log"
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

function Test-HubRequiresToken {
    param([int]$OnPort)
    $node = (Get-Command node -ErrorAction Stop).Source
    $probe = Join-Path $root 'lib\probe-hub-auth.mjs'
    $result = & $node $probe --port $OnPort --expect-reject
    return ($LASTEXITCODE -eq 0)
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

$null = Ensure-ChromeBridgeAuth -Mode $Mode
$extensionId = Get-ChromeBridgeExtensionId -Mode $Mode
$token = Get-ChromeBridgeToken -Mode $Mode
if ([string]::IsNullOrWhiteSpace($token)) {
    Write-Output 'FAILED:hub token missing from local.json chromeBridge (not printed)'
    exit 1
}
if ([string]::IsNullOrWhiteSpace($extensionId)) {
    Write-Output 'FAILED:hub extension-id missing'
    exit 1
}

$existing = Test-HubPid
if ($existing) {
    $rejectsUnauth = $false
    try { $rejectsUnauth = Test-HubRequiresToken -OnPort $port } catch { $rejectsUnauth = $false }
    if ($rejectsUnauth) {
        Write-Output "SUCCESS:hub already pid=$($existing.Id) ws=127.0.0.1:$port token=required extension-id=$extensionId"
        exit 0
    }
    Write-Output "WARN:hub pid=$($existing.Id) accepted an unauthenticated client — restarting with token"
    Stop-Process -Id $existing.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 400
    if (Test-Path -LiteralPath $pidFile) { Remove-Item -LiteralPath $pidFile -Force }
}

$node = (Get-Command node -ErrorAction Stop).Source
$prevToken = $env:CHROME_BRIDGE_TOKEN
$prevExt = $env:CHROME_BRIDGE_EXTENSION_ID
$env:CHROME_BRIDGE_TOKEN = $token
$env:CHROME_BRIDGE_EXTENSION_ID = $extensionId
try {
    $proc = Start-Process -FilePath $node -ArgumentList @(
        $entry,
        '--hub-only',
        '--port', "$port",
        '--extension-id', $extensionId
    ) -PassThru -WindowStyle Hidden -RedirectStandardError $log -RedirectStandardOutput $stdoutLog
} finally {
    if ($null -eq $prevToken) { Remove-Item Env:CHROME_BRIDGE_TOKEN -ErrorAction SilentlyContinue } else { $env:CHROME_BRIDGE_TOKEN = $prevToken }
    if ($null -eq $prevExt) { Remove-Item Env:CHROME_BRIDGE_EXTENSION_ID -ErrorAction SilentlyContinue } else { $env:CHROME_BRIDGE_EXTENSION_ID = $prevExt }
}
$proc.Id | Set-Content -LiteralPath $pidFile -Encoding ascii
Start-Sleep -Milliseconds 800
if ($proc.HasExited) {
    Write-Output "FAILED:hub exited immediately code=$($proc.ExitCode) log=$log"
    exit 1
}
Write-Output "SUCCESS:hub started pid=$($proc.Id) ws=127.0.0.1:$port extension-id=$extensionId token=from-local.json (not printed) log=$log"
exit 0
