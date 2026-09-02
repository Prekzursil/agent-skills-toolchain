param(
    [Parameter(Mandatory = $true)]
    [string]$Root
)
# Independent Get-ChildItem census for IMP-0385. Mechanically different from
# the Python os.scandir walker in tools/router/index_build.py.
$ErrorActionPreference = "Continue"
if (-not (Test-Path -LiteralPath $Root)) {
    Write-Output '{"exists":false,"file_count":0}'
    exit 0
}
$files = @(Get-ChildItem -LiteralPath $Root -Recurse -Force -File -ErrorAction SilentlyContinue)
Write-Output (@{ exists = $true; file_count = $files.Count } | ConvertTo-Json -Compress)
exit 0
