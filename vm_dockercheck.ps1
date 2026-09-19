$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
function W($m) { Write-Output ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }

W '=== Docker processes ==='
Get-Process | Where-Object { $_.Name -match 'docker|Docker' } | ForEach-Object { W ("{0}  PID {1}  start {2}" -f $_.Name, $_.Id, $_.StartTime.ToString('HH:mm:ss')) }

W '=== docker info retry ==='
& docker info 2>&1 | Select-String -Pattern 'Storage Driver|Docker Root Dir|Server Version|Operating System|ERROR|error' | ForEach-Object { W $_.Line }

W '=== wsl distro state ==='
(& wsl -l -v) | ForEach-Object { $c = $_ -replace '[^\x20-\x7E]',''; if ($c -match '\S') { W $c } }

W '=== Docker engine log tail ==='
$logDir = "$env:LOCALAPPDATA\Docker\log\host"
$latest = Get-ChildItem $logDir -Filter *.log -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($latest) {
    W ("latest: {0} ({1})" -f $latest.Name, $latest.LastWriteTime.ToString('HH:mm:ss'))
    Get-Content $latest.FullName -Tail 40 | ForEach-Object { if ($_ -match 'vhdx|disk|location|error|fail|wsl|mount|started|ready' -and $_ -notmatch 'debug') { W $_ } }
} else { W 'no host logs found' }

W '=== settings-store.json DiskImageLocation now ==='
$sj = Get-Content "$env:APPDATA\Docker\settings-store.json" -Raw | ConvertFrom-Json
W ("DiskImageLocation = {0}" -f $sj.DiskImageLocation)
W ("D:\Docker\wsl\disk contents:")
Get-ChildItem 'D:\Docker\wsl' -Recurse -File | ForEach-Object { W ("  {0} = {1:N2} GB" -f $_.FullName, ($_.Length/1GB)) }
