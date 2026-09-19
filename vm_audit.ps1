$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

Write-Output '=== WSL STATUS ==='
$wsl = & wsl -l -v
foreach ($line in $wsl) { Write-Output $line }

Write-Output ''
Write-Output '=== WINDOWS FEATURES (Hyper-V / WSL-relevant) ==='
foreach ($f in @('Microsoft-Windows-Subsystem-Linux','VirtualMachinePlatform','HypervisorPlatform','Microsoft-Hyper-V-All')) {
    $st = (Get-WindowsOptionalFeature -Online -FeatureName $f).State
    Write-Output ("{0} = {1}" -f $f, $st)
}

Write-Output ''
Write-Output '=== DISK FREE ==='
Get-PSDrive -PSProvider FileSystem | Where-Object {$_.Free -ne $null} | ForEach-Object {
    Write-Output ("{0}: used {1:N1} GB / free {2:N1} GB" -f $_.Name, ($_.Used/1GB), ($_.Free/1GB))
}

Write-Output ''
Write-Output '=== VM TREE: D:\VMware VMs (files > 100MB) ==='
Get-ChildItem 'D:\VMware VMs' -Recurse -File | Where-Object {$_.Length -gt 100MB} |
    Sort-Object Length -Descending |
    ForEach-Object { Write-Output ("{0,10:N1} MB  {1}  (modified {2})" -f ($_.Length/1MB), $_.FullName, $_.LastWriteTime.ToString('yyyy-MM-dd')) }

Write-Output ''
Write-Output '=== VM TREE TOTAL ==='
$sum = (Get-ChildItem 'D:\VMware VMs' -Recurse -File | Measure-Object Length -Sum).Sum
Write-Output ("{0:N2} GB" -f ($sum/1GB))

Write-Output ''
Write-Output '=== VMX CONFIG (key settings) ==='
$vmx = 'D:\VMware VMs\Linux_Ubuntu-ova-import\Linux_Ubuntu\Linux_Ubuntu.vmx'
Select-String -Path $vmx -Pattern '^(memsize|numvcpus|cpuid.coresPerSocket|displayName|guestOS|scsi0:0.fileName|ethernet0.connectionType|tools.syncTime)' | ForEach-Object { Write-Output $_.Line }

Write-Output ''
Write-Output '=== LAST VM ACTIVITY (log timestamps) ==='
Get-ChildItem 'D:\VMware VMs' -Recurse -Filter 'vmware.log' | ForEach-Object {
    Write-Output ("{0}  last write {1}  {2:N0} KB" -f $_.FullName, $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm'), ($_.Length/1KB))
}

Write-Output ''
Write-Output '=== SNAPSHOTS / VMSN-VMEM (bloat indicators) ==='
Get-ChildItem 'D:\VMware VMs' -Recurse -Include '*.vmsn','*.vmem','*-00000*.vmdk' -File | ForEach-Object {
    Write-Output ("{0,10:N1} MB  {1}" -f ($_.Length/1MB), $_.FullName)
}

Write-Output ''
Write-Output '=== VMware install size ==='
$vi = (Get-ChildItem 'C:\Program Files (x86)\VMware' -Recurse -File | Measure-Object Length -Sum).Sum
Write-Output ("{0:N2} GB" -f ($vi/1GB))

Write-Output ''
Write-Output '=== Other VM locations sanity check ==='
foreach ($p in @("$envUSERPROFILE\Documents\Virtual Machines", 'C:\Users\Prekzursil\Documents\Virtual Machines', 'D:\VMs')) {
    if (Test-Path $p) { Write-Output "EXISTS: $p" } else { Write-Output "absent: $p" }
}
