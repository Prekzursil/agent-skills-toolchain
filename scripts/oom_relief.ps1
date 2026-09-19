$ErrorActionPreference = 'SilentlyContinue'

function Snapshot($label) {
  $o = Get-CimInstance Win32_OperatingSystem
  $m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
  "{0}: FreeRAM={1}GB  PagedPool={2}GB  NonPagedPool={3}GB  Committed={4}GB" -f `
    $label, [math]::Round($o.FreePhysicalMemory/1MB,1), [math]::Round($m.PoolPagedBytes/1GB,1),
    [math]::Round($m.PoolNonpagedBytes/1GB,1), [math]::Round($m.CommittedBytes/1GB,1)
}

Snapshot "BEFORE"

# --- 1. Docker: is anything actually running? ---
"`n=== docker ps ==="
$dp = docker ps --format '{{.Names}} {{.Status}}' 2>&1
if ($LASTEXITCODE -eq 0) {
  if ($dp) { $dp } else { "(no running containers)" }
} else { "docker CLI unavailable/wedged: $dp" }

# --- 2. Quit Docker Desktop + WSL VM ---
if (-not $dp -or $LASTEXITCODE -ne 0) {
  "`n=== stopping Docker Desktop ==="
  Get-Process 'Docker Desktop','com.docker.backend','docker' | Stop-Process -Force
  Start-Sleep -Seconds 4
  wsl --shutdown
  Start-Sleep -Seconds 4
  Snapshot "AFTER Docker/WSL shutdown"
} else {
  "`n(!) containers running - skipping Docker shutdown"
}

# --- 3. NordVPN service restart (releases leaked pool if driver-tagged) ---
"`n=== NordVPN service restart ==="
Get-Service | Where-Object { $_.DisplayName -like '*NordVPN*' -or $_.Name -like '*nordvpn*' } |
  ForEach-Object { "service: $($_.Name) status=$($_.Status)" }
Get-Process 'nordvpn-service','nordvpn' | Select-Object Name, Id | Format-Table -AutoSize

# graceful service restart
$svc = Get-Service | Where-Object { $_.Name -like '*nordvpn*' } | Select-Object -First 1
if ($svc) {
  Restart-Service $svc.Name -Force
  Start-Sleep -Seconds 5
  "service $svc restarted"
}
# kill leftover userland nordvpn processes (tray app etc., auto-restarts on demand)
Get-Process 'nordvpn' | Where-Object { $_.Name -ne 'nordvpn-service' } | Stop-Process -Force
Start-Sleep -Seconds 3
Snapshot "AFTER NordVPN restart"

""
"=== final top-8 private hogs ==="
Get-Process | Sort-Object PrivateMemorySize64 -Descending | Select-Object -First 8 Name, Id,
  @{n='Priv_MB';e={[math]::Round($_.PrivateMemorySize64/1MB)}} | Format-Table -AutoSize
