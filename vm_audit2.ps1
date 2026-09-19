$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

Write-Output '=== WSL DISTROS (registry Lxss) ==='
$lxs = Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss'
foreach ($k in $lxs) {
    $p = Get-ItemProperty $k.PSPath
    $state = ''
    try { $state = switch ($p.State) { 1 {'Running'} 3 {'Stopped'} default {"State $($p.State)"} } } catch { $state = '?' }
    Write-Output ("{0}  [{1}]  base={2}" -f $p.DistributionName, $state, $p.BasePath)
    $bp = $p.BasePath -replace '^\\\\\?\\',''
    Get-ChildItem $bp -Filter *.vhdx -File | ForEach-Object {
        Write-Output ("    ext4.vhdx = {0:N2} GB  (modified {1})" -f ($_.Length/1GB), $_.LastWriteTime.ToString('yyyy-MM-dd'))
    }
}

Write-Output ''
Write-Output '=== WSL service ==='
Get-Service LxssManager, wslservice | ForEach-Object { Write-Output ("{0} = {1}" -f $_.Name, $_.Status) }

Write-Output ''
Write-Output '=== VMware processes running now ==='
Get-Process vmware-vmx, vmware, vmware-tray -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Output ("{0}  PID {1}  WS {2:N0} MB  start {3}" -f $_.Name, $_.Id, ($_.WorkingSet64/1MB), $_.StartTime.ToString('yyyy-MM-dd HH:mm'))
}
if (-not (Get-Process vmware-vmx -ErrorAction SilentlyContinue)) { Write-Output 'vmware-vmx NOT running (VM is suspended, not live)' }

Write-Output ''
Write-Output '=== VM log history (all rotations) ==='
Get-ChildItem 'D:\VMware VMs\Linux_Ubuntu-ova-import\Linux_Ubuntu' -Filter 'vmware*.log' | Sort-Object LastWriteTime -Descending |
    Select-Object -First 8 | ForEach-Object { Write-Output ("{0}  {1}  {2:N0} KB" -f $_.Name, $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm'), ($_.Length/1KB)) }

Write-Output ''
Write-Output '=== VMDK descriptor (virtual size / format) ==='
$fs = [System.IO.File]::OpenRead('D:\VMware VMs\Linux_Ubuntu-ova-import\Linux_Ubuntu\Linux_Ubuntu-disk1.vmdk')
$buf = New-Object byte[] 4096
$fs.Read($buf, 0, 4096) | Out-Null
$fs.Close()
$txt = [System.Text.Encoding]::ASCII.GetString($buf)
foreach ($line in ($txt -split "`n")) {
    if ($line -match 'ddb\.(virtualSize|geometry|adapterType|createType)|version=|CID=') { Write-Output $line.Trim() }
}

Write-Output ''
Write-Output '=== VM folder: all files ==='
Get-ChildItem 'D:\VMware VMs\Linux_Ubuntu-ova-import\Linux_Ubuntu' -File | Sort-Object Length -Descending | ForEach-Object {
    Write-Output ("{0,12:N1} MB  {1}  {2}" -f ($_.Length/1MB), $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm'), $_.Name)
}

Write-Output ''
Write-Output '=== WSL kernel/version ==='
$wslver = & wsl --version
foreach ($line in $wslver) { Write-Output $line }
