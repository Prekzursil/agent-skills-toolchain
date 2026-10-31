<#
.SYNOPSIS
  account-hopper launcher: the hands of the rotation loop.

.DESCRIPTION
  Wraps a resumable job with automatic account rotation. The ledger
  (account_hopper.py) decides which account is next and never switches or
  touches the network; this script is the caller that acts on the answer:

    hop -> set MODAL_PROFILE -> run your job -> on non-zero exit treat the
    account as drained, record the run, hop to the next -> resume.
    Job exit 0 stops the loop (done); the ledger's exit 3 stops it (rotation
    dry); -MaxHops caps the loop for a human look.

  The phenibut gotcha is handled here, automatically: MODAL_TOKEN_* env vars
  override ~/.modal.toml and would pin every call to one account no matter
  what MODAL_PROFILE says, so they are unset before the first run.

  Relaying checkpointed job state across accounts (Modal volumes are
  per-workspace) stays the job's own business - see the README's rotation
  section.

.EXAMPLE
  .\hopper_launch.ps1 -Config cfg.json -CostEstimateUsd 8 -JobId gpn-run1 `
    -Job 'modal run D:\Research\projects\phenibut\compute\modal_scripts\atm_modal_resumable.py --cmd gpn'
#>
param(
  [Parameter(Mandatory = $true)][string]$Config,
  [Parameter(Mandatory = $true)][string]$Job,
  [string]$Ledger = "",
  [double]$CostEstimateUsd = 0,
  [string]$JobId = "",
  [int]$MaxHops = 12
)

$ErrorActionPreference = 'Continue'
$tool = Join-Path $PSScriptRoot 'account_hopper.py'
if (-not (Test-Path $tool)) {
  Write-Error "account_hopper.py not found next to this script: $tool"
  exit 2
}
if (-not $JobId) { $JobId = 'job-' + (Get-Date -Format 'yyyyMMdd-HHmmss') }

$base = @('--config', $Config)
if ($Ledger) { $base += @('--ledger', $Ledger) }

function Invoke-Hop {
  param([string]$Account = '', [double]$Usd = 0)
  $hopArgs = @('hop')
  if ($Account) { $hopArgs += @('--account', $Account, '--usd', "$Usd") }
  $out = & python $tool @base @hopArgs
  if ($LASTEXITCODE -eq 0) { return (@($out) | Select-Object -Last 1) }
  return $null
}

Remove-Item Env:MODAL_TOKEN_ID, Env:MODAL_TOKEN_SECRET -ErrorAction SilentlyContinue

$current = Invoke-Hop
if (-not $current) {
  Write-Host '[hopper] rotation is dry before anything started (ledger exit 3).'
  exit 3
}
Write-Host "[hopper] job '$JobId' starting on profile: $current"

$hop = 0
while ($true) {
  $hop++
  if ($hop -gt $MaxHops) {
    Write-Host "[hopper] MaxHops ($MaxHops) reached - stopping for a human look."
    exit 4
  }
  $env:MODAL_PROFILE = $current
  Write-Host "[hopper] hop $hop on $current (MODAL_PROFILE set)"
  # $Job arrives as a string (a scriptblock cannot survive the pwsh -File
  # process boundary) and runs in a CHILD pwsh: the job cannot kill this loop
  # with its own exit semantics, and $LASTEXITCODE is the child's exit code.
  # MODAL_PROFILE is inherited.
  & pwsh -NoProfile -Command $Job
  $jobRc = $LASTEXITCODE

  if ($jobRc -eq 0) {
    Write-Host '[hopper] job returned success - recording and stopping.'
    if ($CostEstimateUsd -gt 0) {
      & python $tool @base record --account $current --usd "$CostEstimateUsd" --job-id "$JobId-hop$hop" | Out-Null
    }
    else {
      Write-Warning 'no -CostEstimateUsd given: this run spend is NOT in the ledger; the next rotation will over-estimate budget.'
    }
    exit 0
  }

  Write-Host "[hopper] job exited rc=$jobRc on $current - treating the account as drained, hopping."
  $next = Invoke-Hop -Account $current -Usd $CostEstimateUsd
  if (-not $next) {
    Write-Host '[hopper] rotation is DRY (ledger exit 3) - stopping.'
    exit 3
  }
  if ($CostEstimateUsd -le 0) {
    Write-Warning 'no -CostEstimateUsd: hopped WITHOUT a spend record - this run is invisible to the ledger.'
  }
  Write-Host "[hopper] hopping: $current -> $next"
  $current = $next
}
