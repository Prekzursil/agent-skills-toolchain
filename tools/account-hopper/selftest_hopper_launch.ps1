<#
Self-test for hopper_launch.ps1. Runs the launcher twice against stub jobs and
temp configs, asserting the three loop endings:

  A. switch-then-done: account a is drained (stub exits 1), the launcher hops
     to b, the stub succeeds, the loop exits 0 with both runs recorded.
  B. dry: a single-account config where the stub always fails; after the first
     drain the ledger says dry and the launcher exits 3.

Exit 0 = all assertions held. No network, no real Modal, no real config.
#>
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("hopper-selftest-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$failures = @()

function New-Config([string]$name, [object[]]$accounts) {
  $path = Join-Path $tmp $name
  @{ global_ceiling_usd = 10.0; min_headroom_usd = 0.1; accounts = $accounts } |
    ConvertTo-Json -Depth 5 | Set-Content -Path $path -Encoding utf8
  return $path
}

$stub = Join-Path $tmp 'jobstub.ps1'
@'
if ($env:MODAL_PROFILE -eq 'acct-a') { Write-Host "stub: would be drained on $($env:MODAL_PROFILE)"; exit 1 }
Write-Host "stub: completed on $($env:MODAL_PROFILE)"; exit 0
'@ | Set-Content -Path $stub -Encoding utf8

# --- Run A: switch-then-done -------------------------------------------------
$cfgA = New-Config 'cfgA.json' @(
  @{ profile = 'acct-a'; cap_usd = 1.0; funded = $true }
  @{ profile = 'acct-b'; cap_usd = 1.0; funded = $true }
)
$ledA = Join-Path $tmp 'ledA.jsonl'
$outA = & pwsh -NoProfile -File (Join-Path $here 'hopper_launch.ps1') `
  -Config $cfgA -Ledger $ledA -CostEstimateUsd 0.5 -JobId selftest-A `
  -Job "& pwsh -NoProfile -File $stub" 2>&1
$rcA = $LASTEXITCODE
$flatA = ($outA | Out-String)
if ($rcA -ne 0) { $failures += "A: expected exit 0, got $rcA" }
if ($flatA -notmatch 'hopping: acct-a -> acct-b') { $failures += "A: no a->b hop in output" }
if ($flatA -notmatch 'job returned success') { $failures += "A: no success stop" }
$linesA = @(Get-Content $ledA -ErrorAction SilentlyContinue)
# Honest drain sequence: a holds $1.00 and the floor is $0.10, so the launcher
# drains a twice ($0.50 each, still above the floor after the first) before the
# ledger hands over to b. Three recorded runs, a twice then b once.
if ($linesA.Count -ne 3) { $failures += "A: expected 3 ledger entries, got $($linesA.Count)" }
$usdA = @($linesA | ForEach-Object { ($_ | ConvertFrom-Json).usd } )
if (($usdA | Measure-Object -Sum).Sum -ne 1.5) { $failures += "A: expected $1.50 total recorded, got $(($usdA | Measure-Object -Sum).Sum)" }

# --- Run B: dry ---------------------------------------------------------------
$cfgB = New-Config 'cfgB.json' @(
  @{ profile = 'acct-solo'; cap_usd = 1.0; funded = $true }
)
$ledB = Join-Path $tmp 'ledB.jsonl'
$outB = & pwsh -NoProfile -File (Join-Path $here 'hopper_launch.ps1') `
  -Config $cfgB -Ledger $ledB -CostEstimateUsd 0.5 -JobId selftest-B `
  -Job 'exit 1' 2>&1
$rcB = $LASTEXITCODE
$flatB = ($outB | Out-String)
if ($rcB -ne 3) { $failures += "B: expected exit 3 (dry), got $rcB" }
if ($flatB -notmatch 'rotation is DRY') { $failures += "B: no dry stop in output" }

if ($failures.Count) {
  Write-Host "SELFTEST FAILED:"
  $failures | ForEach-Object { Write-Host "  - $_" }
  exit 1
}
Write-Host "SELFTEST PASS: switch-then-done (A) and dry (B) both behaved; temp dir $tmp"
exit 0
