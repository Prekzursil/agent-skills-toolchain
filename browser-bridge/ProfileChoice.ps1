# Estate browser-automation launchers dot-source this.
# Contract: PROFILE-CHOICE.md (mandatory a/b/c before any run).

Set-StrictMode -Version Latest

function Show-ProfileChoices {
    Write-Host '--- browser profile choice (mandatory, G-90) ---'
    Write-Host '(a) live              -Profile live              OWNER OVERRIDE of G-90 for THIS run only. Real Chrome/Edge. No relaunch, no kill.'
    Write-Host '(b) agent-persistent  -Profile agent-persistent  DEFAULT. Dedicated profile; logins persist; never wiped.'
    Write-Host '(c) agent-ephemeral   -Profile agent-ephemeral  Throwaway profile; wiped after this run.'
    Write-Host 'Persistent paths: ~\.agents\browser-profiles\{chrome,edge,firefox,tor}-agent'
}

function Test-InteractiveStdin {
    try {
        if ([Console]::IsInputRedirected) { return $false }
        return [Environment]::UserInteractive
    } catch {
        return $false
    }
}

function Resolve-BrowserProfileChoice {
    param(
        [string]$Profile,
        [string]$Purpose = 'browser-automation'
    )
    Show-ProfileChoices
    if ([string]::IsNullOrWhiteSpace($Profile)) {
        if (Test-InteractiveStdin) {
            $answer = Read-Host "Choice for ${Purpose} [a/b/c, Enter=b]"
            $Profile = switch -Regex ($answer.Trim()) {
                '^(a|live)$' { 'live' }
                '^(c|agent-ephemeral|ephemeral)$' { 'agent-ephemeral' }
                default { 'agent-persistent' }
            }
            Write-Host "selected_via=prompt profile=$Profile"
        } else {
            Write-Output 'FAILED:profile-choice -Profile is required in non-interactive runs. Pass live | agent-persistent | agent-ephemeral.'
            return $null
        }
    }
    $normalized = switch -Regex ($Profile.Trim()) {
        '^(a|live)$' { 'live' }
        '^(b|agent-persistent|persistent)$' { 'agent-persistent' }
        '^(c|agent-ephemeral|ephemeral)$' { 'agent-ephemeral' }
        default { $null }
    }
    if (-not $normalized) {
        Write-Output "FAILED:profile-choice unknown -Profile '$Profile'"
        return $null
    }
    Write-Host "g90=$(if ($normalized -eq 'live') { 'OVERRIDDEN-THIS-RUN' } else { 'honored' }) profile=$normalized"
    return $normalized
}

function Get-EstateRoot {
    Join-Path $env:USERPROFILE '.agents\browser-bridge'
}

function Get-ProfilesRoot {
    Join-Path $env:USERPROFILE '.agents\browser-profiles'
}

function Get-PersistentProfileDir {
    param([ValidateSet('chrome', 'edge', 'firefox', 'tor')][string]$Kind)
    Join-Path (Get-ProfilesRoot) "$Kind-agent"
}

function New-EphemeralProfileDir {
    param([ValidateSet('chrome', 'edge', 'firefox', 'tor')][string]$Kind)
    $root = Join-Path (Get-ProfilesRoot) 'ephemeral'
    if (-not (Test-Path -LiteralPath $root)) {
        New-Item -ItemType Directory -Path $root | Out-Null
    }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $dir = Join-Path $root "$Kind-$stamp-$PID"
    New-Item -ItemType Directory -Path $dir | Out-Null
    return $dir
}

function Ensure-PersistentProfileDir {
    param([string]$Dir)
    if (-not (Test-Path -LiteralPath $Dir)) {
        New-Item -ItemType Directory -Path $Dir | Out-Null
        Write-Host "profile_created=true path=$Dir"
    } else {
        if (Test-Path -LiteralPath $Dir -PathType Leaf) {
            throw "profile path is a file: $Dir"
        }
        Write-Host "profile_created=false path=$Dir persist=never-wipe"
    }
}
