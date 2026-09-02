# Refuse push if this private-only repo has been flipped public.
# Install: Copy-Item .\scripts\git-hooks\pre-push-private-guard.ps1 .git\hooks\pre-push
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
exit 0
