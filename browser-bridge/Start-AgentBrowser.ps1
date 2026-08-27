<#
.SYNOPSIS
    Launch or attach the estate Chrome/Edge automation lane.

.DESCRIPTION
    Mandatory -Profile (live | agent-persistent | agent-ephemeral). See PROFILE-CHOICE.md.
    Dedicated profiles persist across runs. LIVE never relaunches or kills the owner's browser.
    Extension-bridge via chrome.debugger; no OS keystroke injection; loopback binds only.

.PARAMETER Profile
    Required in non-interactive runs. Interactive omission prompts; Enter = agent-persistent.

.PARAMETER Stop
    Stop ONLY processes whose CommandLine contains this run's dedicated profile dir.
    Refuses to stop live/default Chrome or Edge.
#>
[CmdletBinding()]
param(
    [ValidateSet('chrome', 'edge')]
    [string]$Browser = 'chrome',

    [string]$Profile,

    [switch]$Stop,

    [switch]$Status,

    [ValidateRange(5, 180)]
    [int]$TimeoutSec = 90
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'ProfileChoice.ps1')

function Write-Terminal {
    param([ValidateSet('SUCCESS', 'FAILED')][string]$State, [string]$Detail)
    Write-Output "${State}:agent-browser $Detail"
}

$BROWSER_EXES = @{
    chrome = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
    )
    edge   = @(
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
    )
}
$PROCESS_NAMES = @{ chrome = 'chrome'; edge = 'msedge' }
$CDP_PORTS = @{ chrome = 9224; edge = 9334 }
$AGENT_HUB_PORT = 8770
$LIVE_HUB_PORT = 8790

function Resolve-BrowserExe {
    param([string]$Kind)
    foreach ($candidate in $BROWSER_EXES[$Kind]) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) { return $candidate }
    }
    throw "no $Kind executable found"
}

function Get-MatchingBrowserProcesses {
    param([string]$Kind, [string]$ProfileDir, [int]$CdpPort)
    $name = $PROCESS_NAMES[$Kind]
    $needle = $ProfileDir.TrimEnd('\')
    Get-Process -Name $name -ErrorAction SilentlyContinue | Where-Object {
        if (-not $_.CommandLine) { return $false }
        $cl = $_.CommandLine
        if ($CdpPort -and $cl.Contains("--remote-debugging-port=$CdpPort")) { return $true }
        return ($cl.IndexOf($needle, [StringComparison]::OrdinalIgnoreCase) -ge 0)
    }
}

function Test-LoopbackPortOpen {
    param([int]$Port)
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $iar = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(400)
        if ($ok) { $client.EndConnect($iar) | Out-Null; $client.Close(); return $true }
        $client.Close()
        return $false
    } catch {
        return $false
    }
}

function Get-CdpVersion {
    param([int]$OnPort)
    $req = @{
        Uri             = "http://127.0.0.1:$OnPort/json/version"
        UseBasicParsing = $true
        TimeoutSec      = 2
        ErrorAction     = 'Stop'
    }
    if ($PSVersionTable.PSVersion.Major -ge 6) { $req['NoProxy'] = $true }
    try { return (Invoke-WebRequest @req).Content } catch { return $null }
}

try {
    $choice = Resolve-BrowserProfileChoice -Profile $Profile -Purpose "$Browser-automation"
    if (-not $choice) { Write-Terminal FAILED 'profile choice missing or invalid'; exit 2 }

    $extensionDir = Join-Path (Get-EstateRoot) 'extension-agent'
    if (-not (Test-Path -LiteralPath (Join-Path $extensionDir 'manifest.json'))) {
        Write-Terminal FAILED "extension not found at $extensionDir"
        exit 1
    }

    $hubPort = if ($choice -eq 'live') { $LIVE_HUB_PORT } else { $AGENT_HUB_PORT }
    $cdpPort = $CDP_PORTS[$Browser]
    Write-Output "browser=$Browser"
    Write-Output "hub_port=$hubPort"
    Write-Output "bind=127.0.0.1"

    if ($choice -eq 'live') {
        Write-Output 'live_policy=no-relaunch no-kill no-load-extension-flag'
        Write-Output "live_extension_port_in_popup_must_be=$LIVE_HUB_PORT"
        if ($Stop) {
            Write-Terminal FAILED 'refusing -Stop on live profile (would risk the owner browser)'
            exit 1
        }
        if ($Status) {
            $hubUp = Test-LoopbackPortOpen -Port $hubPort
            Write-Output "hub_listening=$hubUp"
            Write-Terminal SUCCESS 'live status only (owner browser not inspected for kill/launch)'
            exit 0
        }
        Write-Output 'action=attach-only'
        Write-Terminal SUCCESS "live mode: start hub on 127.0.0.1:$hubPort separately; do not launch $Browser"
        exit 0
    }

    if ($choice -eq 'agent-ephemeral') {
        $profileDir = New-EphemeralProfileDir -Kind $Browser
    } else {
        $profileDir = Get-PersistentProfileDir -Kind $Browser
        Ensure-PersistentProfileDir -Dir $profileDir
    }
    Write-Output "user_data_dir=$profileDir"
    Write-Output "wipe=$(if ($choice -eq 'agent-ephemeral') { 'after-stop' } else { 'never' })"

    $readyFile = Join-Path $PSScriptRoot "logs\$Browser-agent.ready.json"
    $stopFile = Join-Path $PSScriptRoot "logs\$Browser-agent.stop"
    $launcherOut = Join-Path $PSScriptRoot "logs\$Browser-agent.stdout.log"
    $launcherErr = Join-Path $PSScriptRoot "logs\$Browser-agent.stderr.log"

    if ($Stop) {
        if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'logs'))) {
            New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot 'logs') | Out-Null
        }
        Set-Content -LiteralPath $stopFile -Value 'stop' -Encoding ascii
        if (Test-Path -LiteralPath $readyFile) {
            try {
                $ready = Get-Content -LiteralPath $readyFile -Raw | ConvertFrom-Json
                if ($ready.pid) {
                    Stop-Process -Id ([int]$ready.pid) -Force -ErrorAction SilentlyContinue
                    Write-Output "stopped_launcher_pid=$($ready.pid)"
                }
            } catch {}
        }
        $mine = @(Get-MatchingBrowserProcesses -Kind $Browser -ProfileDir $profileDir -CdpPort $cdpPort)
        foreach ($proc in $mine) {
            Write-Output "stopping pid=$($proc.Id) ws_mb=$([int]($proc.WorkingSet64/1MB))"
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 800
        if ($choice -eq 'agent-ephemeral' -and (Test-Path -LiteralPath $profileDir)) {
            Remove-Item -LiteralPath $profileDir -Recurse -Force -ErrorAction SilentlyContinue
            Write-Output 'ephemeral_wiped=true'
        }
        Write-Terminal SUCCESS "stopped launcher + $($mine.Count) $Browser process(es) for this profile only"
        exit 0
    }

    $existing = @(Get-MatchingBrowserProcesses -Kind $Browser -ProfileDir $profileDir -CdpPort $cdpPort)
    if ($Status) {
        Write-Output "agent_procs=$($existing.Count)"
        Write-Output "ready_file=$(Test-Path -LiteralPath $readyFile)"
        Write-Output "hub=$(if (Test-LoopbackPortOpen -Port $hubPort) { 'up' } else { 'down' })"
        Write-Terminal SUCCESS 'status'
        exit 0
    }

    if ((Test-Path -LiteralPath $readyFile) -and $existing.Count -gt 0) {
        Write-Output "reused_pids=$($existing.Id -join ',')"
        Write-Terminal SUCCESS "already running dedicated $Browser for this profile (not relaunched)"
        exit 0
    }

    Write-Output 'launch_via=playwright-pipe Extensions.loadUnpacked'
    Write-Output 'flags=anti-throttle,enable-unsafe-extension-debugging,no-http-cdp-port'
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'logs'))) {
        New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot 'logs') | Out-Null
    }
    foreach ($stale in @($readyFile, $stopFile)) {
        if (Test-Path -LiteralPath $stale) { Remove-Item -LiteralPath $stale -Force }
    }
    $py = (Get-Command python -ErrorAction Stop).Source
    $launcher = Join-Path $PSScriptRoot 'lib\launch-agent.py'
    $proc = Start-Process -FilePath $py -ArgumentList @(
        $launcher,
        '--browser', $Browser,
        '--user-data-dir', $profileDir,
        '--extension-dir', $extensionDir,
        '--ready-file', $readyFile,
        '--stop-file', $stopFile
    ) -PassThru -WindowStyle Hidden -RedirectStandardOutput $launcherOut -RedirectStandardError $launcherErr

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if ($proc.HasExited) {
            Write-Terminal FAILED "launcher exited early code=$($proc.ExitCode) err=$launcherErr"
            exit 1
        }
        if (Test-Path -LiteralPath $readyFile) { break }
        Start-Sleep -Milliseconds 400
    }
    if (-not (Test-Path -LiteralPath $readyFile)) {
        Write-Terminal FAILED "launcher pid=$($proc.Id) did not write ready file after ${TimeoutSec}s"
        exit 1
    }
    $ready = Get-Content -LiteralPath $readyFile -Raw | ConvertFrom-Json
    $listed = @($ready.extensions.extensions)
    Write-Output "launcher_pid=$($proc.Id)"
    Write-Output "extension_id=$($ready.loaded.id)"
    Write-Output "extensions_listed=$($listed.Count)"
    if ($listed.Count -lt 1) {
        Write-Terminal FAILED 'Extensions.getExtensions empty after pipe loadUnpacked'
        exit 1
    }
    Write-Terminal SUCCESS "launched $Browser profile=$choice dir=$profileDir hub=127.0.0.1:$hubPort extension=$($ready.loaded.id)"
    exit 0
} catch {
    Write-Terminal FAILED "$($_.Exception.Message)"
    exit 1
}
