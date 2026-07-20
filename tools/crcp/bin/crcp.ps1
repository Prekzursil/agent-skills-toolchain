# CRCP CLI launcher (Windows)
# Usage: .\bin\crcp.ps1 health
#        .\bin\crcp.ps1 auth status
#        .\bin\crcp.ps1 chatgpt list
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $PSScriptRoot '..\crcp\__main__.py'))) {
    $Root = Split-Path -Parent $PSScriptRoot
}
$ToolsCrp = Split-Path -Parent $PSScriptRoot
# Ensure tools/crcp is on PYTHONPATH so `crcp` package imports
$env:PYTHONPATH = $ToolsCrp + [IO.Path]::PathSeparator + ($env:PYTHONPATH ?? '')
python -m crcp @Args
exit $LASTEXITCODE
