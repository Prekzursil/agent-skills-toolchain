[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory = $true)]
    [string]$ReportPath,

    [Parameter(Mandatory = $true)]
    [string]$AllowedRoot,

    [Parameter(Mandatory = $true)]
    [string]$QuarantineRoot,

    [string]$WorkspaceRoot = 'C:\Users\Prekzursil'
)

$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath($WorkspaceRoot)
$allowed = [IO.Path]::GetFullPath($AllowedRoot).TrimEnd('\') + '\'
$quarantine = [IO.Path]::GetFullPath($QuarantineRoot).TrimEnd('\') + '\'

if (-not $allowed.StartsWith($workspace.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw "AllowedRoot must be inside WorkspaceRoot: $allowed"
}
if (-not $quarantine.StartsWith($workspace.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw "QuarantineRoot must be inside WorkspaceRoot: $quarantine"
}

$findings = @(Get-Content -LiteralPath $ReportPath -Raw | ConvertFrom-Json)
$byFile = $findings | Group-Object File
$records = [System.Collections.Generic.List[object]]::new()
$entropy = [Text.Encoding]::UTF8.GetBytes('agents-secret-evidence-v1')

foreach ($group in $byFile) {
    $relativeInput = [string]$group.Name
    $source = if ([IO.Path]::IsPathRooted($relativeInput)) {
        [IO.Path]::GetFullPath($relativeInput)
    } else {
        [IO.Path]::GetFullPath((Join-Path $workspace $relativeInput))
    }
    if (-not $source.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Finding path escaped AllowedRoot: $source"
    }
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        continue
    }

    $relative = [IO.Path]::GetRelativePath($allowed.TrimEnd('\'), $source)
    $destination = Join-Path $quarantine ($relative + '.dpapi')
    $destinationFull = [IO.Path]::GetFullPath($destination)
    if (-not $destinationFull.StartsWith($quarantine, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Quarantine path escaped QuarantineRoot: $destinationFull"
    }

    if (-not $PSCmdlet.ShouldProcess($source, 'DPAPI-protect and remove plaintext')) {
        continue
    }

    $plain = [IO.File]::ReadAllBytes($source)
    $sha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($plain)).ToLowerInvariant()
    $protected = [Security.Cryptography.ProtectedData]::Protect(
        $plain,
        $entropy,
        [Security.Cryptography.DataProtectionScope]::CurrentUser
    )
    $parent = Split-Path -Parent $destinationFull
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $temporary = $destinationFull + '.tmp'
    [IO.File]::WriteAllBytes($temporary, $protected)
    [IO.File]::Move($temporary, $destinationFull, $true)

    $roundTrip = [Security.Cryptography.ProtectedData]::Unprotect(
        [IO.File]::ReadAllBytes($destinationFull),
        $entropy,
        [Security.Cryptography.DataProtectionScope]::CurrentUser
    )
    $roundTripHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($roundTrip)).ToLowerInvariant()
    if ($roundTripHash -ne $sha256) {
        throw "DPAPI verification failed for $source"
    }

    [IO.File]::Delete($source)
    $records.Add([ordered]@{
        original_path = [IO.Path]::GetRelativePath($workspace, $source).Replace('\', '/')
        sha256 = $sha256
        bytes = $plain.Length
        encrypted_path = [IO.Path]::GetRelativePath($workspace, $destinationFull).Replace('\', '/')
        rule_ids = @($group.Group.RuleID | Sort-Object -Unique)
    })
}

$manifest = [ordered]@{
    schema_version = 1
    protected_at = [DateTimeOffset]::UtcNow.ToString('o')
    protection = 'Windows DPAPI CurrentUser'
    records = $records
}
[IO.Directory]::CreateDirectory($quarantine.TrimEnd('\')) | Out-Null
$manifestPath = Join-Path $quarantine 'manifest.json'
$manifestTemporary = $manifestPath + '.tmp'
$manifestJson = $manifest | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText($manifestTemporary, $manifestJson + "`n", [Text.UTF8Encoding]::new($false))
[IO.File]::Move($manifestTemporary, $manifestPath, $true)

Write-Output "SUCCESS:secret-artifacts-protected files=$($records.Count) manifest=$manifestPath"
