# modal_hopper_launch.ps1 — the auto-hop loop over longhaul's per-account runner.
#
# Owner directive 2026-10-30: the phenibut-grade automatic hop (drain one Modal
# account, move to the next funded one) is restored CALLER-SIDE as this thin
# wrapper. The longhaul core stays manual-by-design (see MIGRATION.md §1); this
# script only loops `longhaul run` across the config's funded accounts, so all
# budgeting, pausing and recording still flows through the core tool.
#
# Name rationale (same directive): this wrapper is Modal-specific (MODAL_PROFILE
# rotation), hence modal-hopper. The longhaul core (budget math, checkpoint,
# config schema) stays provider-general.
#
# Usage (phenibut example):
#   pwsh -File tools\longhaul\modal_hopper_launch.ps1 `
#     -Config D:\Research\projects\phenibut\compute\hopper\cfg.json `
#     -CostEstimateUsd 8 -JobId gpn-run1 `
#     -Job 'modal run D:\Research\projects\phenibut\compute\modal_scripts\atm_modal_resumable.py --cmd gpn'
#
# Exit codes mirror longhaul: 0 = job done; 3 = every funded account is drained
# or paused (rotation dry); other non-zero = the job itself failed on the last
# account tried.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Config,
    [Parameter(Mandatory = $true)][string]$Job,
    [string]$StateDir = "",
    [double]$CostEstimateUsd = 0,
    [string]$JobId = "",
    [int]$MaxHops = 0,
    [string]$Python = "python"
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$core = Join-Path $here 'longhaul.py'
if (-not (Test-Path $core)) { Write-Error "longhaul.py not found beside this launcher: $core"; exit 2 }
if (-not (Test-Path $Config)) { Write-Error "config not found: $Config"; exit 2 }

# --- NAME-PROPERNESS PRE-FLIGHT --------------------------------------------
# Every enrolled profile must exist as a configured profile in ~/.modal.toml,
# otherwise a hop would silently run against an unconfigured account.
$modalToml = Join-Path $env:USERPROFILE '.modal.toml'
$modalProfiles = @()
if (Test-Path $modalToml) {
    foreach ($line in Get-Content $modalToml) {
        if ($line -match '^\s*\[([^\]]+)\]\s*$') { $modalProfiles += $Matches[1] }
    }
}
$cfg = Get-Content $Config -Raw | ConvertFrom-Json
$funded = @($cfg.accounts | Where-Object { $null -eq $_.funded -or $true -eq $_.funded -or $false -eq $_.closed })
if ($funded.Count -eq 0) { Write-Error "no funded accounts in $Config"; exit 3 }
$unknown = @($funded | Where-Object { $_.profile -notin $modalProfiles })
if ($unknown.Count -gt 0) {
    Write-Error ("name mismatch — these enrolled profiles are NOT in ~\.modal.toml: " +
        (($unknown | ForEach-Object profile) -join ', ') +
        ". Fix cfg.json or add the profiles; refusing to hop blind.")
    exit 2
}
Write-Host ("modal-hopper pre-flight OK: {0} funded profile(s), all present in ~\.modal.toml" -f $funded.Count)

if ($MaxHops -le 0 -or $MaxHops -gt $funded.Count) { $MaxHops = $funded.Count }

# --- THE HOP LOOP -----------------------------------------------------------
$hop = 0
$lastExit = 3
foreach ($acct in $funded) {
    if ($hop -ge $MaxHops) { break }
    if ($true -eq $acct.closed) { continue }
    $p = $acct.profile
    $hop++
    Write-Host ("[modal-hopper] hop {0}/{1} -> profile '{2}'" -f $hop, $MaxHops, $p)
    $args = @($core, '--config', $Config)
    if ($StateDir) { $args += @('--state-dir', $StateDir) }
    $args += @('run', '--profile', $p)
    if ($CostEstimateUsd -gt 0) { $args += @('--projected-usd', "$CostEstimateUsd") }
    $args += @('--')
    $args += @($Job -split '\s+')
    & $Python @args
    $lastExit = $LASTEXITCODE
    if ($lastExit -eq 0) { Write-Host "[modal-hopper] job completed on '$p' (exit 0)"; exit 0 }
    if ($lastExit -ne 3) { Write-Host "[modal-hopper] job failed on '$p' with exit $lastExit — aborting rotation"; exit $lastExit }
    Write-Host "[modal-hopper] '$p' drained or paused (exit 3) — hopping"
    # Checkpoint relay between workspaces is intentionally manual (Modal volumes
    # are per-workspace); see the job's own resume flags, e.g. RE_SETUP=NO for ATM.
}
Write-Host "[modal-hopper] rotation dry after $hop hop(s) (exit 3)"
exit 3
