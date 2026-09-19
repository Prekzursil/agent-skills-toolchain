$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

Write-Output '=== Stopping VMware processes ==='
Get-Process vmware, vmware-tray, vmware-vmx -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Output ("killing {0} (PID {1})" -f $_.Name, $_.Id)
    Stop-Process -Id $_.Id -Force
}
Start-Sleep -Seconds 3
$left = Get-Process vmware, vmware-tray, vmware-vmx -ErrorAction SilentlyContinue
if ($left) { $left | ForEach-Object { Write-Output ("STILL ALIVE: {0} {1}" -f $_.Name, $_.Id) } }
else { Write-Output 'All VMware processes stopped.' }

Write-Output ''
Write-Output '=== Resetting VMware inventory (removes VM registration) ==='
$inv = "$env:APPDATA\VMware\inventory.vmls"
Remove-Item $inv -Force
Write-Output ("inventory.vmls deleted: {0}" -f (-not (Test-Path $inv)))

Write-Output ''
Write-Output '=== Deleting D:\VMware VMs\Linux_Ubuntu-ova-import (212.6 GB) ==='
$before = (Get-PSDrive D).Free
Remove-Item 'D:\VMware VMs\Linux_Ubuntu-ova-import' -Recurse -Force
$after = (Get-PSDrive D).Free
Write-Output ("Folder still exists: {0}" -f (Test-Path 'D:\VMware VMs\Linux_Ubuntu-ova-import'))
Write-Output ("D: free before {0:N1} GB -> after {1:N1} GB  (reclaimed {2:N1} GB)" -f ($before/1GB), ($after/1GB), (($after-$before)/1GB))

Write-Output ''
Write-Output '=== Bonus audit: D:\VirtualBox VMs size ==='
$s = (Get-ChildItem 'D:\VirtualBox VMs' -Recurse -File | Measure-Object Length -Sum).Sum
Write-Output ("{0:N2} GB" -f ($s/1GB))
Get-ChildItem 'D:\VirtualBox VMs' -Recurse -File | Where-Object { $_.Length -gt 200MB } | Sort-Object Length -Descending |
    ForEach-Object { Write-Output ("{0,10:N1} MB  {1}  (modified {2})" -f ($_.Length/1MB), $_.FullName, $_.LastWriteTime.ToString('yyyy-MM-dd')) }
# is VirtualBox even installed?
$vbox = Test-Path 'C:\Program Files\Oracle\VirtualBox\VirtualBox.exe'
$vbox2 = Test-Path 'C:\Program Files\VirtualBox\VirtualBox.exe'
Write-Output ("VirtualBox installed: Program Files\Oracle = {0}, Program Files\VirtualBox = {1}" -f $vbox, $vbox2)

Write-Output ''
Write-Output '=== Bonus audit: other vhdx/vmdk/vdi scattered on D: (depth 3) ==='
Get-ChildItem 'D:\' -Include *.vhdx,*.vmdk,*.vdi -File -Recurse -Depth 3 | Where-Object { $_.Length -gt 500MB } |
    ForEach-Object { Write-Output ("{0,10:N1} GB  {1}" -f ($_.Length/1GB), $_.FullName) }
