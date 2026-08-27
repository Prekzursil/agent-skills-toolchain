[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$python = 'C:\Python314\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $cmd = Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $cmd) { throw 'Python 3 is required for openrouter-complete' }
    $python = $cmd.Source
}
$script = Join-Path $PSScriptRoot 'openrouter-complete.py'
& $python $script @args
exit $LASTEXITCODE
