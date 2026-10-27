param(
  [string]$BundlePath = "$PSScriptRoot\private-env.windows.json"
)
$ErrorActionPreference = 'Stop'
if (!(Test-Path $BundlePath)) { throw "Missing env bundle: $BundlePath" }
$data = Get-Content $BundlePath -Raw | ConvertFrom-Json -Depth 10
foreach ($entry in $data.variables.PSObject.Properties) {
  [Environment]::SetEnvironmentVariable($entry.Name, [string]$entry.Value, 'User')
  [Environment]::SetEnvironmentVariable($entry.Name, [string]$entry.Value, 'Machine')
  Set-Item -Path ("Env:" + $entry.Name) -Value ([string]$entry.Value)
}
Write-Host ("Applied {0} variables to User + Machine scope." -f $data.variables.PSObject.Properties.Count)
