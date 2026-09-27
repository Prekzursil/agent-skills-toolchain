<#
  Fresh-process launcher for supervise.ps1 used by the self-test.

  WHY THIS EXISTS (measured 2026-09-25, this box):
    pwsh -File script.ps1 -Arr a b c   ->  $Arr.Count = 1   (only 'a' arrives)
    pwsh -File script.ps1 -Arr a,b,c   ->  $Arr.Count = 1   (one element "a,b,c")
  `pwsh -File` CANNOT bind a multi-element array parameter. Space-separated tokens silently
  drop everything after the first, which would have made the self-test's -StartArgs a one-element
  array and every control a lie. In-process splatting (`& $script @hashtable`) binds correctly
  (verified Count=2) and `exit N` inside it propagates to $LASTEXITCODE (verified 7).

  So: the harness writes the parameter set as JSON, and THIS script - itself a fresh OS process,
  which is what keeps the durability controls honest - splats it in-process.
#>
param(
    [Parameter(Mandatory = $true)][string]$ParamFile,
    [Parameter(Mandatory = $true)][string]$Script
)
$ErrorActionPreference = 'Stop'
$h = @{}
foreach ($p in ((Get-Content -LiteralPath $ParamFile -Raw -Encoding utf8 | ConvertFrom-Json).PSObject.Properties)) {
    $h[$p.Name] = $p.Value
}
& $Script @h
exit $LASTEXITCODE
