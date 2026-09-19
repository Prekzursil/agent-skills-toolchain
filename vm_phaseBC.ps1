$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$log = 'C:\Users\Prekzursil\.agents\phaseBC.log'
function W($m) { $line = ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m); Write-Output $line; Add-Content $log $line }

# ---------- 0) Kick off Win11 ISO download in background (network-only) ----------
W '=== Phase 0: Fido + ISO download (background) ==='
$fido = "$env:USERPROFILE\.agents\Fido.ps1"
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/pbatard/Fido/master/Fido.ps1' -OutFile $fido -UseBasicParsing
    $isoUrl = & $fido -Win 11 -Rel Latest -Arch x64 -Ed Pro -Lang English -GetUrl
    W ("ISO URL obtained: {0}" -f ($isoUrl | Select-Object -First 1))
    New-Item -ItemType Directory -Path 'D:\ISOs' -Force | Out-Null
    $bits = Start-Process -FilePath 'bitsadmin.exe' -ArgumentList '/transfer','Win11ISO','/download','/priority','LOW',$isoUrl,'D:\ISOs\Win11_x64.iso' -NoNewWindow -PassThru
    W ("bitsadmin PID {0} downloading ISO" -f $bits.Id)
} catch { W ("ISO prep FAILED: {0}" -f $_.Exception.Message) }

# ---------- 1) Stop Docker Desktop completely ----------
W '=== Phase 1: stopping Docker Desktop ==='
$dn = @('Docker Desktop','com.docker.backend','com.docker.build','com.docker.dev-envs','com.docker.service','docker','dockerd','docker-proxy','wsl-relay')
foreach ($n in $dn) { Get-Process -Name $n -ErrorAction SilentlyContinue | ForEach-Object { W ("kill {0} PID {1}" -f $_.Name, $_.Id); Stop-Process -Id $_.Id -Force } }
Stop-Service com.docker.service -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 5

# ---------- 2) Full WSL shutdown, verify locks released ----------
W '=== Phase 2: wsl --shutdown ==='
& wsl --shutdown 2>&1 | Out-Null
Start-Sleep -Seconds 10
$vhdxU = 'C:\Users\Prekzursil\AppData\Local\Packages\CanonicalGroupLimited.Ubuntu_79rhkp1fndgsc\LocalState\ext4.vhdx'
$vhdxD = 'C:\Users\Prekzursil\AppData\Local\Docker\wsl\disk\docker_data.vhdx'
foreach ($v in @($vhdxU, $vhdxD)) {
    try { $fs = [IO.File]::Open($v, 'Open', 'Read', 'None'); $fs.Close(); W ("UNLOCKED: {0}" -f $v) }
    catch { W ("STILL LOCKED: {0} -- {1}" -f $v, $_.Exception.Message) }
}

# ---------- 3) Move Ubuntu to D:\WSL\Ubuntu ----------
W '=== Phase 3: wsl --manage Ubuntu --move ==='
$freeC0 = (Get-PSDrive C).Free
W ("C: free before: {0:N1} GB" -f ($freeC0/1GB))
& wsl --manage Ubuntu --move D:\WSL\Ubuntu 2>&1 | Out-File "$env:USERPROFILE\.agents\wsl_move3.log" -Encoding Unicode
$mv = [Text.Encoding]::Unicode.GetString([IO.File]::ReadAllBytes("$env:USERPROFILE\.agents\wsl_move3.log")) -replace '[^\x20-\x7E\r\n]',''
W ("move rc={0} out={1}" -f $LASTEXITCODE, $mv.Trim())
$key = (Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' | Where-Object { (Get-ItemProperty $_.PSPath).DistributionName -eq 'Ubuntu' })
$p2 = Get-ItemProperty $key.PSPath
W ("POST-MOVE BasePath: {0}  DefaultUid: {1}" -f $p2.BasePath, $p2.DefaultUid)

# sparse trim while stopped
if ($p2.BasePath -like 'D:*') {
    & wsl --manage Ubuntu --set-sparse true 2>&1 | Out-File "$env:USERPROFILE\.agents\wsl_sparse2.log" -Encoding Unicode
    $sp = [Text.Encoding]::Unicode.GetString([IO.File]::ReadAllBytes("$env:USERPROFILE\.agents\wsl_sparse2.log")) -replace '[^\x20-\x7E\r\n]',''
    W ("sparse out: {0}" -f $sp.Trim())
    Get-ChildItem 'D:\WSL\Ubuntu' -Filter *.vhdx -File | ForEach-Object { W ("vhdx on D: {0} = {1:N2} GB" -f $_.Name, ($_.Length/1GB)) }
}

# ---------- 4) Move docker_data.vhdx to D:\Docker\wsl\disk ----------
W '=== Phase 4: Docker data disk move ==='
New-Item -ItemType Directory -Path 'D:\Docker\wsl\disk' -Force | Out-Null
robocopy 'C:\Users\Prekzursil\AppData\Local\Docker\wsl\disk' 'D:\Docker\wsl\disk' 'docker_data.vhdx' /NJH /NJS /NP /NFL /NDL /NS /NC 2>&1 | Out-Null
W ("robocopy rc={0}" -f $LASTEXITCODE)
$newD = 'D:\Docker\wsl\disk\docker_data.vhdx'
if ((Test-Path $newD) -and ((Get-Item $newD).Length -eq (Get-Item $vhdxD).Length)) {
    W 'Copy verified byte-size match; removing source vhdx'
    Remove-Item $vhdxD -Force
} else { W 'WARNING: copy mismatch - source kept, aborting docker repoint'; exit 1 }

# repoint Docker settings
$ss = "$env:APPDATA\Docker\settings-store.json"
$sj = Get-Content $ss -Raw | ConvertFrom-Json
W ("settings keys containing disk/data/wsl/folder: " + ((($sj.PSObject.Properties | Where-Object { $_.Name -match 'isk|ata|wsl|older|ocation' }) | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ' | '))
if ($sj.PSObject.Properties.Name -contains 'DiskImageLocation') { $sj.DiskImageLocation = 'D:\Docker\wsl' }
else { $sj | Add-Member -NotePropertyName DiskImageLocation -NotePropertyValue 'D:\Docker\wsl' }
Copy-Item $ss "$ss.bak-20260919" -Force
$sj | ConvertTo-Json -Depth 10 | Set-Content $ss -Encoding UTF8
W 'settings-store.json updated (backup at settings-store.json.bak-20260919)'

# ---------- 5) Restart Docker Desktop ----------
W '=== Phase 5: restart Docker Desktop ==='
Start-Service com.docker.service -ErrorAction SilentlyContinue
Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
W 'Docker Desktop launched; engine check in 75s...'
Start-Sleep -Seconds 75
& docker info 2>&1 | Select-String -Pattern 'Storage Driver|Docker Root Dir|Server Version' | ForEach-Object { W $_.Line }
& docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' 2>&1 | Select-Object -First 10 | ForEach-Object { W $_ }

# ---------- 6) Final verification ----------
W '=== Phase 6: final state ==='
$freeC1 = (Get-PSDrive C).Free
$freeD1 = (Get-PSDrive D).Free
W ("C: free now {0:N1} GB (was {1:N1} at start)" -f ($freeC1/1GB), ($freeC0/1GB))
W ("D: free now {0:N1} GB" -f ($freeD1/1GB))
if (Test-Path 'D:\ISOs\Win11_x64.iso') {
    $sz = (Get-Item 'D:\ISOs\Win11_x64.iso').Length
    W ("ISO progress: {0:N2} GB downloaded so far" -f ($sz/1GB))
}
# Ubuntu functional check last (starts distro, fine now)
$out = & wsl -d Ubuntu -e sh -c 'echo WSL_OK; whoami; df -h / | tail -1'
foreach ($l in $out) { $clean = $l -replace '[^\x20-\x7E]',''; if ($clean -match '\S') { W $clean } }
W 'PHASE B+C COMPLETE'
