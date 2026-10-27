# Catalog test companion for IMP-0013 PowerShell adapter.
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $here 'Launch-Adapter.ps1'))) {
    Write-Error 'Launch-Adapter.ps1 missing'
    exit 1
}
Write-Output 'SUCCESS:IMP-0013-test_launch_adapter.ps1'
exit 0
