<#
.SYNOPSIS
    On-demand Tor Browser automation lane (Marionette / tbselenium). Dry-run unless -Launch.
#>
[CmdletBinding()]
param(
    [string]$Profile,
    [switch]$Launch
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'ProfileChoice.ps1')
. (Join-Path $PSScriptRoot 'lib\BridgeAuth.ps1')

$choice = Resolve-BrowserProfileChoice -Profile $Profile -Purpose 'tor-automation'
if (-not $choice) { Write-Output 'FAILED:tor-lane profile choice missing'; exit 2 }
if ($choice -eq 'live') {
    Write-Output 'FAILED:tor-lane LIVE Tor Browser UI is refused (do not drive the human TB session)'
    exit 2
}

$tbb = Join-Path $env:USERPROFILE 'Desktop\Tor Browser'
$tbbExe = Join-Path $tbb 'Browser\firefox.exe'
$profileDir = if ($choice -eq 'agent-ephemeral') {
    New-EphemeralProfileDir -Kind tor
} else {
    $dir = Get-PersistentProfileDir -Kind tor
    Ensure-PersistentProfileDir -Dir $dir
    $dir
}
Assert-AgentProfileDir -Dir $profileDir

$torRunning = [bool](Get-Process -Name tor -ErrorAction SilentlyContinue)
Write-Output "tbb_path=$tbb"
Write-Output "tbb_exe_exists=$(Test-Path -LiteralPath $tbbExe)"
Write-Output "tor_exe_running=$torRunning"
Write-Output "socks_expected=127.0.0.1:9150"
Write-Output "profile_dir=$profileDir"
Write-Output "second_tor_exe=never"

if (-not $Launch) {
    Write-Output 'SUCCESS:tor-lane on-demand dry-run (not launched)'
    exit 0
}

if ($torRunning) {
    Write-Output 'FAILED:tor-lane refusing -Launch because tor.exe is already running (do not start a second Tor)'
    exit 1
}

Write-Output 'FAILED:tor-lane -Launch is implemented as a documented owner step; this stand-up leaves it unused to avoid disturbing the desktop'
exit 3
