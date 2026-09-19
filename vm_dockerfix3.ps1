$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
function W($m) { Write-Output ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }

W '=== 1) Full stop ==='
foreach ($n in @('Docker Desktop','com.docker.backend','com.docker.build','com.docker.dev-envs','docker','dockerd')) {
    Get-Process -Name $n -ErrorAction SilentlyContinue | ForEach-Object { W ("kill {0} {1}" -f $_.Name, $_.Id); Stop-Process -Id $_.Id -Force }
}
Stop-Service com.docker.service -Force -ErrorAction SilentlyContinue
& wsl --shutdown 2>&1 | Out-Null
Start-Sleep -Seconds 10

W '=== 2) Move main distro folder C: -> D: ==='
New-Item -ItemType Directory -Path 'D:\Docker\wsl\main' -Force | Out-Null
robocopy "$env:LOCALAPPDATA\Docker\wsl\main" 'D:\Docker\wsl\main' /E /MOVE /NJH /NJS /NP /NFL /NDL 2>&1 | Out-Null
W ("robocopy rc={0}" -f $LASTEXITCODE)
Get-ChildItem 'D:\Docker\wsl\main' -Recurse -File | ForEach-Object { W ("D: main file: {0} {1:N0} KB" -f $_.Name, ($_.Length/1KB)) }

W '=== 3) Remove regenerable C: disk ==='
Remove-Item "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx" -Force -ErrorAction SilentlyContinue
W ("C: disk exists: {0}" -f (Test-Path "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx"))

W '=== 4) Repoint docker-desktop distro BasePath in Lxss registry ==='
$dk = Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' | Where-Object { (Get-ItemProperty $_.PSPath).DistributionName -eq 'docker-desktop' }
if ($dk) {
    Set-ItemProperty -Path $dk.PSPath -Name BasePath -Value 'D:\Docker\wsl\main'
    W ("BasePath now: {0}" -f (Get-ItemProperty $dk.PSPath).BasePath)
} else { W 'docker-desktop distro key not found!' }

W '=== 5) Ensure settings wslDataFolder intact ==='
$ss = "$env:APPDATA\Docker\settings-store.json"
$j = Get-Content $ss -Raw | ConvertFrom-Json
if ($j.wslDataFolder -ne 'D:\Docker\wsl') {
    if ($j.PSObject.Properties.Name -contains 'wslDataFolder') { $j.wslDataFolder = 'D:\Docker\wsl' }
    else { $j | Add-Member -NotePropertyName wslDataFolder -NotePropertyValue 'D:\Docker\wsl' }
    [IO.File]::WriteAllText($ss, ($j | ConvertTo-Json -Depth 10), (New-Object System.Text.UTF8Encoding($false)))
}
W ("wslDataFolder = {0}" -f ((Get-Content $ss -Raw | ConvertFrom-Json).wslDataFolder))

W '=== 6) Start Docker Desktop ==='
Start-Service com.docker.service -ErrorAction SilentlyContinue
Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
W 'waiting 150s...'
Start-Sleep -Seconds 150

W '=== 7) Verify ==='
& docker info 2>&1 | Select-String -Pattern 'Server Version' | ForEach-Object { W $_.Line }
& docker images --format '{{.Repository}}:{{.Tag}}  {{.Size}}' 2>&1 | Select-Object -First 30 | ForEach-Object { W ("img: {0}" -f $_) }
& docker system df 2>&1 | ForEach-Object { W ("df: {0}" -f $_) }
W '--- disk heat ---'
Get-Item 'D:\Docker\wsl\disk\docker_data.vhdx' -ErrorAction SilentlyContinue | ForEach-Object { W ("D: data vhdx: {0:N2} GB  modified {1}" -f ($_.Length/1GB), $_.LastWriteTime.ToString('HH:mm:ss')) }
Get-Item 'D:\Docker\wsl\main\ext4.vhdx' -ErrorAction SilentlyContinue | ForEach-Object { W ("D: main vhdx: {0:N2} GB  modified {1}" -f ($_.Length/1GB), $_.LastWriteTime.ToString('HH:mm:ss')) }
$newC = Get-Item "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx" -ErrorAction SilentlyContinue
if ($newC) { W ("C: NEW data vhdx appeared AGAIN: {0:N2} GB modified {1}" -f ($newC.Length/1GB), $newC.LastWriteTime.ToString('HH:mm:ss')) } else { W 'C: no new data vhdx (GOOD)' }
W '--- distro bases ---'
Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' | ForEach-Object {
    $p = Get-ItemProperty $_.PSPath
    W ("{0} -> {1}" -f $p.DistributionName, $p.BasePath)
}
$c = Get-PSDrive C; $d = Get-PSDrive D
W ("FINAL: C: free {0:N1} GB | D: free {1:N1} GB" -f ($c.Free/1GB), ($d.Free/1GB))
