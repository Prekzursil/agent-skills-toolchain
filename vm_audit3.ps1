$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

Write-Output '=== WSL VERSION ==='
(& wsl --version) | ForEach-Object { ($_ -replace '[^\x20-\x7E]','') } | Where-Object { $_ -match '\S' }

Write-Output ''
Write-Output '=== DOCKER CLI ==='
$dockerExe = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerExe) { $dockerExe = Test-Path 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' }
if ($dockerExe) {
    Write-Output '--- docker system df ---'
    & docker system df 2>&1 | ForEach-Object { Write-Output $_ }
    Write-Output '--- docker images ---'
    & docker images --format '{{.Repository}}:{{.Tag}}  {{.Size}}  created {{.CreatedSince}}' 2>&1 | ForEach-Object { Write-Output $_ }
    Write-Output '--- docker info (storage bits) ---'
    & docker info 2>&1 | Select-String -Pattern 'Storage Driver|Docker Root Dir|Total Memory|Server Version|Operating System' | ForEach-Object { Write-Output $_.Line }
} else {
    Write-Output 'docker CLI not found on PATH'
}

Write-Output ''
Write-Output '=== DOCKER ON-DISK FOOTPRINT ==='
foreach ($p in @('C:\Users\Prekzursil\AppData\Local\Docker', 'C:\ProgramData\DockerDesktop', 'C:\ProgramData\Docker')) {
    if (Test-Path $p) {
        $s = (Get-ChildItem $p -Recurse -File | Measure-Object Length -Sum).Sum
        Write-Output ("{0} = {1:N2} GB" -f $p, ($s/1GB))
    } else { Write-Output ("absent: {0}" -f $p) }
}
Write-Output '--- large files under Docker dirs (>50MB) ---'
foreach ($p in @('C:\Users\Prekzursil\AppData\Local\Docker', 'C:\ProgramData\DockerDesktop', 'C:\ProgramData\Docker')) {
    Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 50MB } |
        ForEach-Object { Write-Output ("{0,10:N1} MB  {1}  (modified {2})" -f ($_.Length/1MB), $_.FullName, $_.LastWriteTime.ToString('yyyy-MM-dd')) }
}

Write-Output ''
Write-Output '=== WSL DISTRO VHDX (incl. docker-data style) ==='
Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' | ForEach-Object {
    $p = Get-ItemProperty $_.PSPath
    $bp = $p.BasePath -replace '^\\\\\?\\',''
    Get-ChildItem $bp -Filter *.vhdx -File -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Output ("{0}  {1}  = {2:N2} GB  (modified {3})" -f $p.DistributionName, $_.FullName, ($_.Length/1GB), $_.LastWriteTime.ToString('yyyy-MM-dd'))
    }
}

Write-Output ''
Write-Output '=== ISO SEARCH (D: depth2 + Downloads + Desktop) ==='
$isoPaths = @()
foreach ($root in @('D:\', "C:\Users\Prekzursil\Downloads", "C:\Users\Prekzursil\Desktop")) {
    $isoPaths += Get-ChildItem $root -Filter *.iso -File -Depth 2 -ErrorAction SilentlyContinue
}
if ($isoPaths) { $isoPaths | ForEach-Object { Write-Output ("{0,10:N1} GB  {1}" -f ($_.Length/1GB), $_.FullName) } }
else { Write-Output 'No ISOs found' }

Write-Output ''
Write-Output '=== D: FREE NOW ==='
$d = Get-PSDrive D; Write-Output ("D: free {0:N1} GB" -f ($d.Free/1GB))
$c = Get-PSDrive C; Write-Output ("C: free {0:N1} GB" -f ($c.Free/1GB))
