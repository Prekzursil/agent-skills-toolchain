# Revert EVERY task wrapped by the 2026-09-17 hide-terminals pass back to its original
# action, restoring each from its pristine XML backup. Idempotent and safe.
# Run elevated (the tasks were created elevated).
$backup = Join-Path $PSScriptRoot 'backup'
$names = Get-ChildItem $backup -Filter *.xml | ForEach-Object { $_.BaseName }
Write-Output ("Reverting {0} task(s)..." -f $names.Count)
& (Join-Path $PSScriptRoot 'hide-terminals.ps1') -Tasks $names -Revert
