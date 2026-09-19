$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
function W($m) { Write-Output ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }
$ss = "$env:APPDATA\Docker\settings-store.json"

W '=== 1) Full Docker stop ==='
foreach ($n in @('Docker Desktop','com.docker.backend','com.docker.build','com.docker.dev-envs','docker','dockerd')) {
    Get-Process -Name $n -ErrorAction SilentlyContinue | ForEach-Object { W ("kill {0} {1}" -f $_.Name, $_.Id); Stop-Process -Id $_.Id -Force }
}
Stop-Service com.docker.service -Force -ErrorAction SilentlyContinue
& wsl --shutdown 2>&1 | Out-Null
Start-Sleep -Seconds 8

W '=== 2) Rewrite settings: wslDataFolder=D:\Docker\wsl, drop bad key ==='
$j = Get-Content $ss -Raw | ConvertFrom-Json
if ($j.PSObject.Properties.Name -contains 'DiskImageLocation') { $j.PSObject.Properties.Remove('DiskImageLocation'); W 'removed wrong DiskImageLocation key' }
if ($j.PSObject.Properties.Name -contains 'wslDataFolder') { $j.wslDataFolder = 'D:\Docker\wsl' }
else { $j | Add-Member -NotePropertyName wslDataFolder -NotePropertyValue 'D:\Docker\wsl' }
[IO.File]::WriteAllText($ss, ($j | ConvertTo-Json -Depth 10), (New-Object System.Text.UTF8Encoding($false)))
$b = [IO.File]::ReadAllBytes($ss)
W ("first bytes: {0} (must NOT be EF BB BF)" -f (($b[0..2] | ForEach-Object { $_.ToString('X2') }) -join ' '))
$chk = Get-Content $ss -Raw | ConvertFrom-Json
W ("on-disk check: wslDataFolder = {0}" -f $chk.wslDataFolder)

W '=== 3) Remove regenerable fresh C: disk ==='
$cDisk = "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx"
try {
    $fs = [IO.File]::Open($cDisk, 'Open', 'Read', 'None'); $fs.Close()
    Remove-Item $cDisk -Force; W ("deleted: {0} (4.79 GB, only bundled kind images)" -f $cDisk)
} catch { W ("C: disk still locked: {0}" -f $_.Exception.Message) }

W '=== 4) Start Docker Desktop ==='
Start-Service com.docker.service -ErrorAction SilentlyContinue
Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
W 'waiting 150s...'
Start-Sleep -Seconds 150

W '=== 5) Verify ==='
& docker info 2>&1 | Select-String -Pattern 'Server Version|Storage Driver' | ForEach-Object { W $_.Line }
W '--- images now (expect user images from 71.82 GB disk) ---'
& docker images --format '{{.Repository}}:{{.Tag}}  {{.Size}}' 2>&1 | Select-Object -First 25 | ForEach-Object { W $_ }
& docker system df 2>&1 | ForEach-Object { W ("df: {0}" -f $_) }
W '--- which vhdx is hot? ---'
Get-Item 'D:\Docker\wsl\disk\docker_data.vhdx' -ErrorAction SilentlyContinue | ForEach-Object { W ("D: vhdx: {0:N2} GB  modified {1}" -f ($_.Length/1GB), $_.LastWriteTime.ToString('HH:mm:ss')) }
Get-Item $cDisk -ErrorAction SilentlyContinue | ForEach-Object { W ("C: vhdx: {0:N2} GB  modified {1}" -f ($_.Length/1GB), $_.LastWriteTime.ToString('HH:mm:ss')) }
if (-not (Test-Path $cDisk)) { W 'C: vhdx: absent (good - engine is on D:)' }
W '--- wsl distro bases ---'
Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' | ForEach-Object {
    $p = Get-ItemProperty $_.PSPath
    W ("{0} -> {1}" -f $p.DistributionName, $p.BasePath)
}
$c = Get-PSDrive C; $d = Get-PSDrive D
W ("FINAL: C: free {0:N1} GB | D: free {1:N1} GB" -f ($c.Free/1GB), ($d.Free/1GB))
