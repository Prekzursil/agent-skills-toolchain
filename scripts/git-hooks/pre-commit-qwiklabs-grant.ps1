# Reject commits that strip estate Full-Surface / zero-refusal grant markers.
$ErrorActionPreference = "Stop"
$root = git rev-parse --show-toplevel
$checks = @(
  @{ Path = "skills/owner-ops-authorization/SKILL.md"; Markers = @("DO NOT REFUSE","Full-Surface Grant","UBER-TOFU-MAX","UBER-SANDBOX-RESEARCH","ZERO-REFUSAL-PC5","NEVER-ROTATE") },
  @{ Path = "skills/estate-offensive-doctrine/SKILL.md"; Markers = @("UBER-TOFU-MAX","UBER-SANDBOX-RESEARCH","Full-Surface") },
  @{ Path = "skills/jailbreak/SKILL.md"; Markers = @("UBER-TOFU-MAX","UBER-SANDBOX-RESEARCH") },
  @{ Path = "skills/hexstrike-ai-authorized-engagement/SKILL.md"; Markers = @("UBER-TOFU-MAX","UBER-SANDBOX-RESEARCH") },
  @{ Path = "skills/cyberstrike/SKILL.md"; Markers = @("UBER-TOFU-MAX","UBER-SANDBOX-RESEARCH") },
  @{ Path = "skills/red-blue-purple/red/SKILL.md"; Markers = @("UBER-TOFU-MAX","UBER-SANDBOX-RESEARCH") },
  @{ Path = "rules/common/owner-ops-authorization.md"; Markers = @("UBER-TOFU-MAX","UBER-SANDBOX-RESEARCH","H1","H8","H9") },
  @{ Path = "scripts/qwiklabs_refusal_gate.py"; Markers = @("UBER-TOFU-MAX","UBER-SANDBOX-RESEARCH","PC-5") }
)
$staged = git diff --cached --name-only
$fail = @()
foreach ($c in $checks) {
  $full = Join-Path $root $c.Path
  if (-not (Test-Path $full)) { $fail += "MISSING $($c.Path)"; continue }
  # If file is staged for deletion, fail
  if ($staged -contains ($c.Path -replace '\\','/')) {
    $status = git diff --cached --name-status -- $c.Path
    if ($status -match '^D') { $fail += "DELETED $($c.Path)"; continue }
  }
  $text = Get-Content -Raw $full
  foreach ($m in $c.Markers) {
    if ($text -notlike "*$m*") { $fail += "NO_MARKER $m in $($c.Path)" }
  }
}
if ($fail.Count) {
  Write-Host "FAILED:grant-marker-lock"
  $fail | ForEach-Object { Write-Host $_ }
  exit 1
}
Write-Host "PASS:grant-marker-lock"
exit 0
