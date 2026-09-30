# Refuse a commit that drops the Qwiklabs / Google Skills zero-refusal markers.
# Other sessions may edit these files. They may not delete the grant.
$ErrorActionPreference = 'Stop'

$required = @{
    'skills/owner-ops-authorization/SKILL.md' = 'ZERO-REFUSAL-PC5'
    'skills/estate-offensive-doctrine/SKILL.md' = 'PC-5'
    'skills/academy-badge-runner/SKILL.md' = 'PC-5'
    'rules/common/owner-ops-authorization.md' = 'Qwiklabs'
    'rules/estate-locks.md' = 'Qwiklabs'
    'scripts/qwiklabs_refusal_gate.py' = 'PASS:qwiklabs-refusal-gate'
}

$staged = @(git diff --cached --name-only)
if (-not $staged) { exit 0 }

$hits = New-Object System.Collections.Generic.List[string]
foreach ($path in $required.Keys) {
    $touched = $staged | Where-Object { $_ -replace '\\','/' -eq $path }
    if (-not $touched) { continue }
    $spec = ':' + $path
    $text = (& git show --no-textconv $spec | Out-String)
    if ($text -notlike ('*' + $required[$path] + '*')) {
        [void]$hits.Add("$path must keep marker $($required[$path])")
    }
}
if ($hits.Count -gt 0) {
    Write-Error ("REFUSING COMMIT: Qwiklabs grant markers removed:`n" + ($hits -join "`n"))
    exit 1
}
exit 0
