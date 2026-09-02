# Token loader for chrome-bridge. Never Write-Output / Write-Host the token value.
Set-StrictMode -Version Latest

$script:AgentExtensionId = 'bdccimcedobipcmhcikcnakjdemiechj'

function Get-LocalJsonPath {
    Join-Path $env:USERPROFILE '.agents\local.json'
}

function Ensure-ChromeBridgeAuth {
    param([ValidateSet('agent', 'live')][string]$Mode = 'agent')
    $py = (Get-Command python -ErrorAction Stop).Source
    $helper = Join-Path $PSScriptRoot 'ensure_bridge_auth.py'
    $json = & $py $helper --mode $Mode
    if ($LASTEXITCODE -ne 0) {
        throw "ensure_bridge_auth.py failed (exit $LASTEXITCODE)"
    }
    return ($json | ConvertFrom-Json)
}

function Get-ChromeBridgeToken {
    param([ValidateSet('agent', 'live')][string]$Mode = 'agent')
    $path = Get-LocalJsonPath
    if (-not (Test-Path -LiteralPath $path)) {
        throw "local.json missing at $path"
    }
    $data = Get-Content -LiteralPath $path -Raw -Encoding utf8 | ConvertFrom-Json
    if (-not $data.chromeBridge) {
        throw "local.json chromeBridge missing"
    }
    $token = if ($Mode -eq 'live') { [string]$data.chromeBridge.liveToken } else { [string]$data.chromeBridge.agentToken }
    if ([string]::IsNullOrWhiteSpace($token) -or $token.Length -lt 16) {
        throw "chromeBridge $Mode token missing or too short"
    }
    return $token
}

function Get-ChromeBridgeExtensionId {
    param([ValidateSet('agent', 'live')][string]$Mode = 'agent')
    if ($Mode -eq 'agent') { return $script:AgentExtensionId }
    $idFile = Join-Path (Split-Path -Parent $PSScriptRoot) 'extension-live\EXTENSION_ID'
    if (Test-Path -LiteralPath $idFile) {
        $id = (Get-Content -LiteralPath $idFile -Raw).Trim()
        if ($id) { return $id }
    }
    $path = Get-LocalJsonPath
    if (Test-Path -LiteralPath $path) {
        $data = Get-Content -LiteralPath $path -Raw -Encoding utf8 | ConvertFrom-Json
        $id = [string]$data.chromeBridge.liveExtensionId
        if ($id) { return $id }
    }
    throw "LIVE extension id not generated yet (extension-live/EXTENSION_ID missing)"
}

function Test-PathIsHumanBrowserProfile {
    param([string]$Dir)
    if ([string]::IsNullOrWhiteSpace($Dir)) { return $false }
    $resolved = [string](Resolve-Path -LiteralPath $Dir -ErrorAction SilentlyContinue)
    if (-not $resolved) { $resolved = $Dir }
    $n = $resolved.ToLowerInvariant()
    $local = [string]$env:LOCALAPPDATA
    $forbidden = @(
        (Join-Path $local 'Google\Chrome\User Data'),
        (Join-Path $local 'Google\Chrome Beta\User Data'),
        (Join-Path $local 'Google\Chrome SxS\User Data'),
        (Join-Path $local 'Microsoft\Edge\User Data'),
        (Join-Path $local 'Microsoft\Edge Beta\User Data'),
        (Join-Path $local 'Microsoft\Edge Dev\User Data'),
        (Join-Path $env:USERPROFILE 'AppData\Local\Google\Chrome\User Data'),
        (Join-Path $env:USERPROFILE 'AppData\Local\Microsoft\Edge\User Data')
    )
    foreach ($f in $forbidden) {
        if ($n.StartsWith($f.ToLowerInvariant())) { return $true }
    }
    return $false
}

function Assert-AgentProfileDir {
    param([string]$Dir)
    if (Test-PathIsHumanBrowserProfile -Dir $Dir) {
        throw "refusing human/default Chrome or Edge User Data path: $Dir"
    }
    $root = [IO.Path]::GetFullPath((Join-Path $env:USERPROFILE '.agents\browser-profiles'))
    $full = [IO.Path]::GetFullPath($Dir)
    $rootPrefix = $root.TrimEnd('\') + '\'
    if (-not ($full.Equals($root, [StringComparison]::OrdinalIgnoreCase) -or $full.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase))) {
        throw "user-data-dir is not under browser-profiles: $Dir"
    }
}
