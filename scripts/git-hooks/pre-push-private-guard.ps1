# Refuse push if this private-only repo has been flipped public,
# or if the commits being pushed contain raw secret files.
# Install: copy to .git/hooks/pre-push (the repo hook execs this file).
$ErrorActionPreference = 'Stop'
$repo = 'Prekzursil/agent-skills-toolchain'

try {
    $json = gh repo view $repo --json isPrivate,visibility | ConvertFrom-Json
} catch {
    Write-Error "pre-push-private-guard: could not query GitHub visibility for $repo"
    exit 1
}
if (-not $json.isPrivate -or $json.visibility -eq 'PUBLIC') {
    Write-Error @"
REFUSING PUSH: $repo visibility is $($json.visibility).
This repository contains browser-profiles (live logins) and personal harness data.
Do not push while public. See SECURITY.md.
"@
    exit 1
}

function Test-SecretName([string]$path) {
    if ([string]::IsNullOrWhiteSpace($path)) { return $false }
    $base = [IO.Path]::GetFileName($path)
    $low = $base.ToLowerInvariant()
    if ($low -in @('.env.example', '.env.template', '.env.sample')) { return $false }
    if ($low -like '*tokeniz*') { return $false }
    if ($low -eq 'local.json') { return $true }
    if ($low -match '\.(pem|key|p12|pfx)$') { return $true }
    if ($low -like '*token*') { return $true }
    return $false
}

$secretHits = New-Object System.Collections.Generic.List[string]
try {
    $stdin = [Console]::In.ReadToEnd()
    foreach ($line in ($stdin -split "`r?`n")) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $parts = $line -split '\s+'
        if ($parts.Count -lt 4) { continue }
        $localSha = $parts[1]
        $remoteSha = $parts[3]
        $range = $null
        if ($remoteSha -match '^0+$') {
            $range = $localSha
        } else {
            $range = "$remoteSha..$localSha"
        }
        $names = git diff-tree --no-commit-id --name-only -r $range 2>$null
        foreach ($n in $names) {
            if (Test-SecretName $n) { [void]$secretHits.Add($n) }
        }
    }
} catch { }

$uniq = $secretHits | Select-Object -Unique
if ($uniq) {
    Write-Error @"
REFUSING PUSH: raw secret filenames in the commits being pushed:
$($uniq -join "`n")
Blocked names: *.key *.pem *.p12 *.pfx *token* local.json
"@
    exit 1
}
exit 0
