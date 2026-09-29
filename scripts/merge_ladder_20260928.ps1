#!/usr/bin/env pwsh
# merge_ladder_20260928.ps1 — self-gating merge ladder: 356 -> 357 -> 355 -> 359.
# Per rung: update-branch (rebase) -> wait battery complete -> REQUIRE target gate(s) green
# AND no NEW red vs the documented inherited-red set -> merge --merge --admin. Stop on any failure.
$ErrorActionPreference = 'Continue'
$env:GH_TOKEN = [Environment]::GetEnvironmentVariable('GITHUB_TOKEN')
$Repo = 'Prekzursil/agent-skills-toolchain'
$Log = 'C:/Users/Prekzursil/.agents/knowledge/audits/MEGAWAVE-CI/ladder-result.txt'
# Inherited reds on main after #360 (documented 2026-09-28; docker-gates = env-gap pending Windows runner)
$Inherited = @('gate-lint-format (ruff)','gate-tests-coverage (python packages)','gate-tests-coverage (platform)','gate-sast (opengrep)','gate-secrets (gitleaks)','gate-deps (osv-scanner)','routing-benchmark (shadow)','gate-skill-dual-write')
# per-PR: target gates that MUST be green (their own fix); others may be inherited-red
$Rungs = @(
    @{ PR = 356; Target = @('gate-secrets (gitleaks)') },
    @{ PR = 357; Target = @('gate-lint-format (ruff)','gate-tests-coverage (python packages)') },
    @{ PR = 355; Target = @('gate-rule-audit') },
    @{ PR = 359; Target = @() }
)
function Get-Checks([string]$Sha) {
    for ($i = 0; $i -lt 80; $i++) {
        Start-Sleep 60
        $json = gh api "repos/$Repo/commits/$Sha/check-runs" --jq '.check_runs[] | .name + "|" + .status + "|" + (.conclusion // "-")' 2>$null
        $map = @{}
        foreach ($l in $json) { $p = $l -split '\|', 3; $map[$p[0]] = @($p[1], $p[2]) }
        $busy = @($map.Keys | Where-Object { $map[$_][0] -ne 'completed' }).Count
        if ($busy -eq 0 -and $map.Count -ge 10) { return $map }
        Add-Content $Log "$(Get-Date -Format HH:mm) PR-rung: $($map.Count) checks, $busy in-flight"
    }
    return $null
}
foreach ($r in $Rungs) {
    $pr = $r.PR
    Add-Content $Log "`n=== RUNG PR #$pr $(Get-Date -Format 'HH:mm') ==="
    gh api -X PUT "repos/$Repo/pulls/$pr/update-branch" -f update_method=rebase 2>&1 | Out-Null
    Start-Sleep 15
    $sha = gh pr view $pr -R $Repo --json headRefOid -q .headRefOid 2>$null
    Add-Content $Log "head=$sha"
    $checks = Get-Checks $sha
    if (-not $checks) { Add-Content $Log "FAILED-LADDER #$pr battery never completed"; break }
    $newRed = @(); $targetMiss = @()
    foreach ($k in $checks.Keys) {
        $concl = $checks[$k][1]
        if ($concl -eq 'failure' -and $Inherited -notcontains $k -and $k -notin @('auto-merge')) { $newRed += $k }
        if ($r.Target -contains $k -and $concl -ne 'success') { $targetMiss += "$k=$concl" }
    }
    Add-Content $Log ("checks: " + (($checks.Keys | ForEach-Object { $_ + '=' + $checks[$_][1] }) -join ' '))
    if ($targetMiss.Count -gt 0) { Add-Content $Log "STOP-LADDER #$pr target gate(s) not green: $($targetMiss -join ',')"; break }
    if ($newRed.Count -gt 0) { Add-Content $Log "STOP-LADDER #$pr NEW red(s): $($newRed -join ',')"; break }
    gh pr merge $pr -R $Repo --merge --admin 2>&1 | ForEach-Object { Add-Content $Log "  merge: $_" }
    $state = gh pr view $pr -R $Repo --json state -q .state 2>$null
    Add-Content $Log "PR #$pr state=$state"
    if ($state -ne 'MERGED') { Add-Content $Log "STOP-LADDER #$pr merge did not land"; break }
    Add-Content $Log "RUNG #$pr MERGED"
}
Add-Content $Log "LADDER-DONE $(Get-Date -Format 'HH:mm')"
