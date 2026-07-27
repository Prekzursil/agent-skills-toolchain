# Durable ChatGPT phone-cookie reapply (isolated Chrome profile)
# Usage:
#   .\reapply.ps1              # apply saved cookies
#   .\reapply.ps1 -Status
#   .\reapply.ps1 -Extract     # pull from phone first (ADB + USB debug Chrome)
#   .\reapply.ps1 -Browser edge -Port 9341

param(
  [switch]$Status,
  [switch]$Extract,
  [ValidateSet("chrome","edge")][string]$Browser = "chrome",
  [int]$Port = 9340
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$apply = Join-Path $here "apply_durable.py"
$bridge = Join-Path $here "cookie_bridge.py"

if ($Status) {
  python $apply status
  exit $LASTEXITCODE
}
if ($Extract) {
  python $bridge extract
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
python $apply apply --browser $Browser --port $Port
exit $LASTEXITCODE
