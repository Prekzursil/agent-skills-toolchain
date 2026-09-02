# IMP-0055: wrap a native command and exit with $LASTEXITCODE (not $?).
# Usage: pwsh -NoProfile -File last_exitcode.ps1 -- python3 -B tools/plugin/cli.py verify
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Argv
)
if (-not $Argv -or $Argv.Count -lt 1) {
    Write-Error "usage: last_exitcode.ps1 -- native [args...]"
    exit 64
}
$cmd = $Argv[0]
$rest = @()
if ($Argv.Count -gt 1) {
    $rest = $Argv[1..($Argv.Count - 1)]
}
& $cmd @rest
$code = $LASTEXITCODE
Write-Output "LASTEXITCODE=$code"
exit $code
