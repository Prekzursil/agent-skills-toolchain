$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
function W($m) { Write-Output ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }

W '=== 1) ISO sanity ==='
$iso = 'D:\ISOs\Win11_x64.iso'
if (-not (Test-Path $iso)) { W 'ISO MISSING - aborting'; exit 1 }
$fi = Get-Item $iso
W ("ISO: {0:N2} GB modified {1}" -f ($fi.Length/1GB), $fi.LastWriteTime.ToString('HH:mm:ss'))
$fs = [IO.File]::OpenRead($iso)
$fs.Seek(0x8000, 'Begin') | Out-Null
$buf = New-Object byte[] 8
$fs.Read($buf, 0, 8) | Out-Null
$fs.Close()
W ("ISO9660 magic at 0x8001: {0} (want 43 44 30 30 31 = CD001)" -f (($buf[1..5] | ForEach-Object { $_.ToString('X2') }) -join ' '))

W '=== 2) Create VM folder + 60GB growable sparse disk ==='
$vmDir = 'D:\VMware VMs\Windows11'
New-Item -ItemType Directory -Path $vmDir -Force | Out-Null
& 'C:\Program Files (x86)\VMware\VMware Workstation\vmware-vdiskmanager.exe' -c -t 0 -s 60GB -a nvme "$vmDir\Windows11.vmdk"
W ("vdiskmanager rc={0}" -f $LASTEXITCODE)
Get-Item "$vmDir\Windows11.vmdk" | ForEach-Object { W ("disk file created: {0:N1} MB on disk" -f ($_.Length/1MB)) }

W '=== 3) Write VMX (Win11, EFI+SecureBoot, auto software vTPM, 4GB/4CPU) ==='
$vmx = @'
.encoding = "UTF-8"
displayName = "Windows11"
guestOS = "windows9-64"
firmware = "efi"
secureBoot.enabled = "TRUE"
managedVM.autoAddVTPM = "software"
memsize = "4096"
numvcpus = "4"
cpuid.coresPerSocket = "2"
nvme0.present = "TRUE"
nvme0:0.present = "TRUE"
nvme0:0.fileName = "Windows11.vmdk"
ide1:0.present = "TRUE"
ide1:0.deviceType = "cdrom-image"
ide1:0.fileName = "D:\ISOs\Win11_x64.iso"
ide1:0.startConnected = "TRUE"
ethernet0.present = "TRUE"
ethernet0.connectionType = "nat"
ethernet0.virtualDev = "e1000e"
ethernet0.addressType = "generated"
usb.present = "TRUE"
ehci.present = "TRUE"
usb_xhci.present = "TRUE"
sound.present = "FALSE"
mks.enable3d = "FALSE"
svga.autosize = "TRUE"
tools.syncTime = "TRUE"
powerType.powerOff = "soft"
powerType.reset = "soft"
powerType.suspend = "hard"
powerType.powerOn = "soft"
uuid.action = "create"
cleanShutdown = "TRUE"
softPowerOff = "FALSE"
'@
[IO.File]::WriteAllText("$vmDir\Windows11.vmx", $vmx, (New-Object System.Text.UTF8Encoding($false)))
W ("VMX written: {0}" -f (Test-Path "$vmDir\Windows11.vmx"))

W '=== 4) Seed VMware inventory entry ==='
$inv = @'
.encoding = "UTF-8"
vmlist1.config = "D:\VMware VMs\Windows11\Windows11.vmx"
vmlist1.DisplayName = "Windows11"
vmlist1.ParentID = "0"
vmlist1.ItemID = "1"
vmlist1.SeqID = "0"
vmlist1.IsFavorite = "FALSE"
vmlist1.IsClone = "FALSE"
vmlist1.CfgVersion = "8"
vmlist1.State = "normal"
vmlist1.IsCfgPathNormalized = "TRUE"
index0.field0.name = "guest"
index0.field0.value = "windows 11 x64"
index0.field0.default = "TRUE"
index0.hostID = "localhost"
index0.id = "D:\VMware VMs\Windows11\Windows11.vmx"
index0.field.count = "1"
index.count = "1"
'@
[IO.File]::WriteAllText("$env:APPDATA\VMware\inventory.vmls", $inv, (New-Object System.Text.UTF8Encoding($false)))
W 'inventory.vmls seeded'

W '=== 5) Final estate state ==='
$c = Get-PSDrive C; $d = Get-PSDrive D
W ("C: free {0:N1} GB | D: free {1:N1} GB" -f ($c.Free/1GB), ($d.Free/1GB))
W ("VM folder contents:")
Get-ChildItem $vmDir | ForEach-Object { W ("  {0}  {1:N1} MB" -f $_.Name, ($_.Length/1MB)) }
W 'PHASE D COMPLETE'
