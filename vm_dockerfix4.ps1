$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
function W($m) { Write-Output ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }
$cWsl = "$env:LOCALAPPDATA\Docker\wsl"
$dWsl = 'D:\Docker\wsl'

W '=== 1) Full stop ==='
foreach ($n in @('Docker Desktop','com.docker.backend','com.docker.build','com.docker.dev-envs','docker','dockerd')) {
    Get-Process -Name $n -ErrorAction SilentlyContinue | ForEach-Object { W ("kill {0} {1}" -f $_.Name, $_.Id); Stop-Process -Id $_.Id -Force }
}
Stop-Service com.docker.service -Force -ErrorAction SilentlyContinue
& wsl --shutdown 2>&1 | Out-Null
Start-Sleep -Seconds 10

W '=== 2) Sync current C: main (fresh, matches live registration) to D: ==='
robocopy "$cWsl\main" "$dWsl\main" /MIR /NJH /NJS /NP /NFL /NDL 2>&1 | Out-Null
W ("main robocopy rc={0}" -f $LASTEXITCODE)

W '=== 3) Replace C: disk folder content with nothing (fresh 4.39G disk is regenerable); keep D: 71.82G original ==='
Get-ChildItem "$cWsl\disk" -File -ErrorAction SilentlyContinue | Remove-Item -Force
W 'C: disk folder emptied'

W '=== 4) Delete C: main + disk dirs, create junctions to D: ==='
Remove-Item "$cWsl\main" -Recurse -Force
Remove-Item "$cWsl\disk" -Recurse -Force
cmd /c mklink /J "$cWsl\main" "$dWsl\main"
cmd /c mklink /J "$cWsl\disk" "$dWsl\disk"
W ("main junction: {0}" -f ((Get-Item "$cWsl\main").LinkTarget))
W ("disk junction: {0}" -f ((Get-Item "$cWsl\disk").LinkTarget))
W '--- sanity: vhdx reachable through junction ---'
Get-Item "$cWsl\disk\docker_data.vhdx" | ForEach-Object { W ("via C: junction: {0:N2} GB" -f ($_.Length/1GB)) }

W '=== 5) Start Docker Desktop ==='
Start-Service com.docker.service -ErrorAction SilentlyContinue
Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
W 'waiting 150s...'
Start-Sleep -Seconds 150

W '=== 6) Verify ==='
& docker info 2>&1 | Select-String -Pattern 'Server Version' | ForEach-Object { W $_.Line }
& docker images --format '{{.Repository}}:{{.Tag}}  {{.Size}}' 2>&1 | Select-Object -First 30 | ForEach-Object { W ("img: {0}" -f $_) }
& docker ps -a --format '{{.Names}} {{.Status}}' 2>&1 | Select-Object -First 15 | ForEach-Object { W ("ctr: {0}" -f $_) }
& docker system df 2>&1 | ForEach-Object { W ("df: {0}" -f $_) }
W '--- heat: is the 71.82G disk live now? ---'
Get-Item "$dWsl\disk\docker_data.vhdx" | ForEach-Object { W ("D: data vhdx: {0:N2} GB modified {1}" -f ($_.Length/1GB), $_.LastWriteTime.ToString('HH:mm:ss')) }
Get-Item "$dWsl\main\ext4.vhdx" | ForEach-Object { W ("D: main vhdx: {0:N2} GB modified {1}" -f ($_.Length/1GB), $_.LastWriteTime.ToString('HH:mm:ss')) }
W '--- real C: usage check (junction adds 0) ---'
$realC = (Get-ChildItem "$env:LOCALAPPDATA\Docker" -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
W ("physical Docker files under C:\AppData\Local\Docker (through junction, should be ~0.1 GB): {0:N2} GB" -f ($realC/1GB))
$c = Get-PSDrive C; $d = Get-PSDrive D
W ("FINAL: C: free {0:N1} GB | D: free {1:N1} GB" -f ($c.Free/1GB), ($d.Free/1GB))
