# gateway-stop.ps1 - stop exactly the gateway process (exact command-line match).
$ErrorActionPreference = "Continue"
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*gateway-server.py*" }
foreach ($p in $procs) {
    Write-Host "stopping pid $($p.ProcessId)"
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
if (-not $procs) { Write-Host "gateway not running." }
