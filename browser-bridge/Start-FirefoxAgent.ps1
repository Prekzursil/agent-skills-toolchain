<#
.SYNOPSIS
    Launch headed Firefox against a dedicated persistent or ephemeral profile (Playwright BiDi).
#>
[CmdletBinding()]
param(
    [string]$Profile,
    [switch]$Stop
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'ProfileChoice.ps1')

$choice = Resolve-BrowserProfileChoice -Profile $Profile -Purpose 'firefox-automation'
if (-not $choice) { Write-Output 'FAILED:firefox-agent profile choice missing'; exit 2 }
if ($choice -eq 'live') {
    Write-Output 'FAILED:firefox-agent LIVE Firefox is not offered (would attach to the owner profile). Use agent-persistent.'
    exit 2
}

$profileDir = if ($choice -eq 'agent-ephemeral') {
    New-EphemeralProfileDir -Kind firefox
} else {
    $dir = Get-PersistentProfileDir -Kind firefox
    Ensure-PersistentProfileDir -Dir $dir
    $dir
}
Write-Output "user_data_dir=$profileDir"
Write-Output "wipe=$(if ($choice -eq 'agent-ephemeral') { 'after-stop' } else { 'never' })"

if ($Stop) {
    Get-Process -Name firefox -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and ($_.CommandLine.IndexOf($profileDir.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase) -ge 0)
    } | ForEach-Object {
        Write-Output "stopping pid=$($_.Id)"
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    if ($choice -eq 'agent-ephemeral' -and (Test-Path -LiteralPath $profileDir)) {
        Remove-Item -LiteralPath $profileDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Output 'ephemeral_wiped=true'
    }
    Write-Output 'SUCCESS:firefox-agent stopped profile-matched processes only'
    exit 0
}

Write-Output "SUCCESS:firefox-agent ready profile=$choice dir=$profileDir (drive via proof/prove-firefox.py)"
exit 0
