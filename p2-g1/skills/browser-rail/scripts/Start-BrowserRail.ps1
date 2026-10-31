<#
.SYNOPSIS
    Idempotently ensure a dedicated CDP-enabled Chrome/Edge profile is running.

.DESCRIPTION
    Chrome 136+ IGNORES --remote-debugging-port when it points at the DEFAULT
    user-data-dir, so "attach to the browser the owner already has open" silently
    does nothing. This launcher runs a SEPARATE automation profile instead, which
    the owner signs into ONCE by hand. No credential ever passes through an agent.

    Idempotent: if a CDP endpoint is already answering on the port AND belongs to
    the requested profile, nothing is launched and the script reports SUCCESS. If
    the port is held by a DIFFERENT profile it reports FAILED rather than
    attaching to whatever happens to be listening.

    The profile directory is created only when absent and is never written to or
    recreated -- the owner's cookies live there.

.PARAMETER Browser
    chrome (default) or edge.

.PARAMETER Port
    CDP port. Bound to loopback by the browser itself; do not expose it.

.PARAMETER ProfileDir
    Automation profile. Defaults to ~/.chrome-automation or ~/.edge-automation.

.PARAMETER Status
    Report the current state and exit without launching anything.

.PARAMETER Stop
    Quit the rail browser -- but ONLY if its --user-data-dir is the rail profile,
    so this can never close the owner's real browser.

.OUTPUTS
    Structured "key=value" lines, then a terminal line:
      SUCCESS:browser-rail <detail>
      FAILED:browser-rail <reason>

.EXAMPLE
    pwsh -File Start-BrowserRail.ps1
    pwsh -File Start-BrowserRail.ps1 -Browser edge -Port 9333
    pwsh -File Start-BrowserRail.ps1 -Status
#>
[CmdletBinding()]
param(
    [ValidateSet('chrome', 'edge')]
    [string]$Browser = 'chrome',

    [ValidateRange(1024, 65535)]
    [int]$Port = 9222,

    [string]$ProfileDir,

    [string]$ExePath,

    [ValidateRange(1, 300)]
    [int]$TimeoutSec = 30,

    [switch]$Status,

    [switch]$Stop
)

$ErrorActionPreference = 'Stop'

# "$State:..." would parse as a drive-qualified variable in PowerShell, hence ${}.
function Write-Terminal {
    param([ValidateSet('SUCCESS', 'FAILED')][string]$State, [string]$Detail)
    Write-Output "${State}:browser-rail $Detail"
}

$BROWSER_EXES = @{
    chrome = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    )
    edge   = @(
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
    )
}
$PROCESS_NAMES = @{ chrome = 'chrome.exe'; edge = 'msedge.exe' }
$DEFAULT_PROFILES = @{
    chrome = Join-Path $HOME '.chrome-automation'
    edge   = Join-Path $HOME '.edge-automation'
}

function Resolve-BrowserExe {
    param([string]$Kind, [string]$Override)
    if ($Override) {
        if (-not (Test-Path -LiteralPath $Override -PathType Leaf)) {
            throw "ExePath not found: $Override"
        }
        return $Override
    }
    foreach ($candidate in $BROWSER_EXES[$Kind]) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return $candidate
        }
    }
    throw "no $Kind executable found; pass -ExePath"
}

function Get-CdpVersion {
    param([int]$OnPort)
    # NOT named $args -- that is a PowerShell automatic variable.
    $req = @{
        Uri             = "http://127.0.0.1:$OnPort/json/version"
        UseBasicParsing = $true
        TimeoutSec      = 3
        ErrorAction     = 'Stop'
    }
    # Loopback must not traverse a configured system proxy (PowerShell 7+).
    if ($PSVersionTable.PSVersion.Major -ge 6) { $req['NoProxy'] = $true }
    try {
        return (Invoke-WebRequest @req).Content | ConvertFrom-Json
    } catch {
        return $null
    }
}

# The rail's OWN parent process: right image name, carries the debug port, and is
# not a --type=renderer child. Filtering by image name also means this probe can
# never match the pwsh process that is running it.
function Get-RailProcess {
    param([string]$Kind, [int]$OnPort)
    $name = $PROCESS_NAMES[$Kind]
    Get-CimInstance Win32_Process -Filter "Name='$name'" -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine -like "*--remote-debugging-port=$OnPort*" -and
            $_.CommandLine -notlike '*--type=*'
        } |
        Select-Object -First 1
}

function Get-CommandLineProfile {
    param([string]$CommandLine)
    if ($CommandLine -match '--user-data-dir=(?:"([^"]+)"|([^\s"]+))') {
        $value = if ($Matches[1]) { $Matches[1] } else { $Matches[2] }
        return $value.TrimEnd('\')
    }
    return $null
}

function Test-SameProfile {
    param([string]$A, [string]$B)
    if (-not $A -or -not $B) { return $false }
    return [string]::Equals($A.TrimEnd('\'), $B.TrimEnd('\'), 'OrdinalIgnoreCase')
}

try {
    if (-not $ProfileDir) { $ProfileDir = $DEFAULT_PROFILES[$Browser] }
    $ProfileDir = $ProfileDir.TrimEnd('\')

    Write-Output "browser=$Browser"
    Write-Output "port=$Port"
    Write-Output "profile=$ProfileDir"

    $existing = Get-RailProcess -Kind $Browser -OnPort $Port
    $existingProfile = if ($existing) { Get-CommandLineProfile $existing.CommandLine } else { $null }

    # ---------------------------------------------------------------- -Stop
    if ($Stop) {
        if (-not $existing) {
            Write-Terminal SUCCESS "nothing to stop (no $Browser on port $Port)"
            exit 0
        }
        if (-not (Test-SameProfile $existingProfile $ProfileDir)) {
            Write-Output "running_profile=$existingProfile"
            Write-Terminal FAILED "refusing to stop pid $($existing.ProcessId): it uses a different profile"
            exit 1
        }
        Stop-Process -Id $existing.ProcessId -Force
        Write-Terminal SUCCESS "stopped rail pid $($existing.ProcessId)"
        exit 0
    }

    $cdp = Get-CdpVersion -OnPort $Port

    # -------------------------------------------------------------- -Status
    if ($Status) {
        if ($cdp) {
            Write-Output "running_profile=$existingProfile"
            Write-Output "cdp_browser=$($cdp.Browser)"
            Write-Output "cdp_ws=$($cdp.webSocketDebuggerUrl)"
            if (Test-SameProfile $existingProfile $ProfileDir) {
                Write-Terminal SUCCESS "rail live on $Port ($($cdp.Browser))"
                exit 0
            }
            Write-Terminal FAILED "port $Port answers but belongs to profile '$existingProfile'"
            exit 1
        }
        Write-Terminal FAILED "no CDP endpoint on port $Port"
        exit 1
    }

    # ------------------------------------------------- already-running path
    if ($cdp) {
        if (Test-SameProfile $existingProfile $ProfileDir) {
            Write-Output "cdp_browser=$($cdp.Browser)"
            Write-Output "cdp_ws=$($cdp.webSocketDebuggerUrl)"
            Write-Output 'launched=false'
            Write-Terminal SUCCESS "already live on $Port ($($cdp.Browser)); reused"
            exit 0
        }
        Write-Output "running_profile=$existingProfile"
        Write-Terminal FAILED "port $Port already held by profile '$existingProfile'; pick another -Port"
        exit 1
    }

    # ------------------------------------------------------------- launch
    $exe = Resolve-BrowserExe -Kind $Browser -Override $ExePath
    Write-Output "exe=$exe"

    # Create ONLY when absent. New-Item -Force on an existing FILE truncates it,
    # and this path may hold the owner's signed-in profile.
    if (-not (Test-Path -LiteralPath $ProfileDir)) {
        New-Item -ItemType Directory -Path $ProfileDir | Out-Null
        Write-Output 'profile_created=true'
    } else {
        if (Test-Path -LiteralPath $ProfileDir -PathType Leaf) {
            Write-Terminal FAILED "profile path is a file, not a directory: $ProfileDir"
            exit 1
        }
        Write-Output 'profile_created=false'
    }

    # This argument list is the configuration measured working with Playwright
    # connect_over_cdp. --remote-debugging-port binds loopback only; do NOT add
    # --remote-debugging-address or --remote-allow-origins=* (both widen access).
    $launchArgs = @(
        "--remote-debugging-port=$Port",
        "--user-data-dir=$ProfileDir",
        '--no-first-run',
        '--no-default-browser-check',
        '--restore-last-session=false',
        'about:blank'
    )
    Start-Process -FilePath $exe -ArgumentList $launchArgs | Out-Null

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $cdp = Get-CdpVersion -OnPort $Port
        if ($cdp) { break }
        Start-Sleep -Milliseconds 400
    }

    if (-not $cdp) {
        Write-Terminal FAILED "no CDP endpoint on port $Port after ${TimeoutSec}s"
        exit 1
    }

    Write-Output "cdp_browser=$($cdp.Browser)"
    Write-Output "cdp_ws=$($cdp.webSocketDebuggerUrl)"
    Write-Output 'launched=true'
    Write-Terminal SUCCESS "launched on $Port ($($cdp.Browser))"
    exit 0
} catch {
    Write-Terminal FAILED "$($_.Exception.Message)"
    exit 1
}
