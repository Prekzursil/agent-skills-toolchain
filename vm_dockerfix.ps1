$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
function W($m) { Write-Output ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }
$ss = "$env:APPDATA\Docker\settings-store.json"

W '=== 1) Kill all Docker processes ==='
foreach ($n in @('Docker Desktop','com.docker.backend','com.docker.build','com.docker.dev-envs','docker','dockerd')) {
    Get-Process -Name $n -ErrorAction SilentlyContinue | ForEach-Object { W ("kill {0} {1}" -f $_.Name, $_.Id); Stop-Process -Id $_.Id -Force }
}
Stop-Service com.docker.service -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 5

W '=== 2) Restore clean settings backup ==='
$bak = "$ss.bak-20260919"
if (Test-Path $bak) {
    Copy-Item $bak $ss -Force
    $b = [IO.File]::ReadAllBytes($ss)
    W ("restored; first bytes: {0}  (EF BB BF = BOM bad)" -f (($b[0..2] | ForEach-Object { $_.ToString('X2') }) -join ' '))
} else { W 'NO BACKUP - reconstructing minimal settings' }

W '=== 3) Scan Docker binaries for settings key name ==='
$binaries = @('C:\Program Files\Docker\Docker\resources\com.docker.backend.exe', 'C:\Program Files\Docker\Docker\Docker Desktop.exe')
$found = @{}
foreach ($exe in $binaries) {
    if (-not (Test-Path $exe)) { W ("absent: {0}" -f $exe); continue }
    $enc = [Text.Encoding]::GetEncoding('ISO-8859-1')
    $txt = [IO.File]::ReadAllText($exe, $enc)
    foreach ($pat in @('DiskImageLocation','diskImageLocation','DataFolder','dataFolder','disk/docker_data','docker_data.vhdx','WslDataFolder')) {
        if ($txt.Contains($pat)) { $found[$pat] = $true; W ("{0} -> contains '{1}'" -f (Split-Path $exe -Leaf), $pat) }
    }
}

W '=== 4) Patch settings with confirmed key (BOM-less) ==='
$j = Get-Content $ss -Raw | ConvertFrom-Json
$keyName = if ($found.ContainsKey('DiskImageLocation')) { 'DiskImageLocation' } elseif ($found.ContainsKey('diskImageLocation')) { 'diskImageLocation' } else { 'DiskImageLocation' }
W ("using key: {0}" -f $keyName)
if ($j.PSObject.Properties.Name -contains $keyName) { $j.$keyName = 'D:\Docker\wsl' }
else { $j | Add-Member -NotePropertyName $keyName -NotePropertyValue 'D:\Docker\wsl' }
$json = ($j | ConvertTo-Json -Depth 10)
[IO.File]::WriteAllText($ss, $json, (New-Object System.Text.UTF8Encoding($false)))
$b2 = [IO.File]::ReadAllBytes($ss)
W ("written; first bytes now: {0}" -f (($b2[0..2] | ForEach-Object { $_.ToString('X2') }) -join ' '))
$chk = Get-Content $ss -Raw | ConvertFrom-Json
W ("verify key on disk: {0} = {1}" -f $keyName, $chk.$keyName)

W '=== 5) Start Docker Desktop ==='
Start-Service com.docker.service -ErrorAction SilentlyContinue
Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
W 'waiting 150s for engine...'
Start-Sleep -Seconds 150
& docker info 2>&1 | Select-String -Pattern 'Storage Driver|Docker Root Dir|Server Version' | ForEach-Object { W $_.Line }
W '--- images ---'
& docker images --format '{{.Repository}}:{{.Tag}}  {{.Size}}' 2>&1 | Select-Object -First 12 | ForEach-Object { W $_ }
W '--- wsl state ---'
(& wsl -l -v) | ForEach-Object { $c = $_ -replace '[^\x20-\x7E]',''; if ($c -match '\S') { W $c } }
W '--- any docker vhdx on C:? ---'
Get-ChildItem "$env:LOCALAPPDATA\Docker" -Recurse -Filter *.vhdx -File -ErrorAction SilentlyContinue | ForEach-Object { W ("{0} = {1:N2} GB" -f $_.FullName, ($_.Length/1GB)) }
$c = Get-PSDrive C; $d = Get-PSDrive D
W ("FINAL: C: free {0:N1} GB | D: free {1:N1} GB" -f ($c.Free/1GB), ($d.Free/1GB))
