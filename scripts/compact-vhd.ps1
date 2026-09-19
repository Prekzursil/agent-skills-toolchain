# Lossless compaction of WSL/Docker dynamic VHDX files. Reclaims free space INSIDE the
# disks back to C: without deleting any data. Stops WSL + Docker briefly. Run elevated.
# Recipe per disk_cleanup_c_drive playbook: fstrim (mark free blocks) -> wsl --shutdown
# -> Mount-VHD -ReadOnly -> Optimize-VHD -Mode Full -> Dismount.
$ErrorActionPreference = 'Continue'
$log = 'D:\vhd-compact_2026-09-18.log'
function Log($m){ $l = "{0}  {1}" -f (Get-Date -f 'HH:mm:ss'), $m; Add-Content $log $l; Write-Output $l }

$targets = @(
  'C:\Users\Prekzursil\AppData\Local\Packages\CanonicalGroupLimited.Ubuntu_79rhkp1fndgsc\LocalState\ext4.vhdx',
  'C:\Users\Prekzursil\AppData\Local\Docker\wsl\disk\docker_data.vhdx'
)
function SizeGB($p){ if(Test-Path $p){ [math]::Round((Get-Item $p).Length/1GB,2) } else { 0 } }

$cBefore = [math]::Round((Get-PSDrive C).Free/1GB,2)
Log "=== compaction start; C: free ${cBefore}GB ==="
foreach($t in $targets){ Log ("  before: {0:N2}GB  {1}" -f (SizeGB $t), (Split-Path $t -Leaf)) }

# 1. fstrim the Ubuntu distro (marks freed ext4 blocks; fstrim lives in /usr/sbin)
Log "fstrim Ubuntu..."
try { $o = wsl.exe -d Ubuntu -u root -e bash -lc 'fstrim -av' 2>&1 | Out-String; Log ("  fstrim: " + $o.Trim()) }
catch { Log "  fstrim error: $($_.Exception.Message)" }

# 2. stop Docker (service + app processes) so docker_data.vhdx is not locked
Log "stopping Docker..."
Get-Service com.docker.service -EA SilentlyContinue | Stop-Service -Force -EA SilentlyContinue
Get-Process -EA SilentlyContinue | Where-Object { $_.Name -match '^(Docker Desktop|com\.docker\.|docker-agent|vpnkit|dockerd|wsl-vpnkit)' } | Stop-Process -Force -EA SilentlyContinue
Start-Sleep -Seconds 3

# 3. shutdown WSL to release vhdx locks
Log "wsl --shutdown..."
wsl.exe --shutdown 2>&1 | Out-Null
Start-Sleep -Seconds 8

# 4. Optimize each vhdx via read-only mount
foreach($t in $targets){
  if(-not (Test-Path $t)){ Log "  MISSING: $t"; continue }
  $name = Split-Path $t -Leaf
  Log "optimizing $name (RO-mount + Optimize-VHD Full)..."
  try {
    Mount-VHD -Path $t -ReadOnly -NoDriveLetter -ErrorAction Stop
    try {
      Optimize-VHD -Path $t -Mode Full -ErrorAction Stop
      Log "  Optimize-VHD Full OK: $name"
    } finally {
      Dismount-VHD -Path $t -ErrorAction SilentlyContinue
    }
  } catch {
    Log "  RO-mount/Optimize failed for ${name}: $($_.Exception.Message)"
    try { Dismount-VHD -Path $t -ErrorAction SilentlyContinue } catch {}
  }
}

$cAfter = [math]::Round((Get-PSDrive C).Free/1GB,2)
foreach($t in $targets){ Log ("  after:  {0:N2}GB  {1}" -f (SizeGB $t), (Split-Path $t -Leaf)) }
Log ("=== compaction end; C: free ${cAfter}GB; RECLAIMED {0:N2}GB ===" -f ($cAfter-$cBefore))
Log "NOTE: WSL/Docker were stopped. Ubuntu auto-starts on next use; relaunch Docker Desktop when needed."
"RECLAIMED={0:N2}GB  C_FREE_AFTER=${cAfter}GB" -f ($cAfter-$cBefore)
