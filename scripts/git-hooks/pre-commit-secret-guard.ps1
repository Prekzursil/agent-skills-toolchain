# Block committing raw secret files (*.key *.pem *token* local.json).
# Wired from .git/hooks/pre-commit.
$ErrorActionPreference = 'Stop'

function Test-SecretName([string]$path) {
    if ([string]::IsNullOrWhiteSpace($path)) { return $false }
    $base = [IO.Path]::GetFileName($path)
    $low = $base.ToLowerInvariant()
    if ($low -in @('.env.example', '.env.template', '.env.sample')) { return $false }
    if ($low -like '*tokeniz*') { return $false }
    if ($low -eq 'local.json') { return $true }
    if ($low -match '\.(pem|key|p12|pfx)$') { return $true }
    if ($low -like '*token*') {
        # Documentation ABOUT tokens (oauth flows, keyvault refs) is not a secret file.
        if ($low -match '\.(md|markdown|mdx|rst|adoc|html?)$') { return $false }
        return $true
    }
    return $false
}

$staged = git diff --cached --name-only -z 2>$null
if (-not $staged) { exit 0 }
$hits = New-Object System.Collections.Generic.List[string]
foreach ($n in ($staged -split "`0")) {
    if (Test-SecretName $n) { [void]$hits.Add($n) }
}
if ($hits.Count -gt 0) {
    Write-Error @"
REFUSING COMMIT: raw secret filenames staged:
$($hits -join "`n")
Blocked names: *.key *.pem *.p12 *.pfx *token* local.json
"@
    exit 1
}
exit 0
