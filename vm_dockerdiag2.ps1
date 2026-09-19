$ErrorActionplorer = $null
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
function W($m) { Write-Output ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }

W '=== raw settings-store.json (keys + disk-ish values) ==='
$raw = Get-Content "$env:APPDATA\Docker\settings-store.json" -Raw
try { $j = $raw | ConvertFrom-Json } catch { W ("JSON parse error: {0}" -f $_.Exception.Message) }
if ($j) {
    foreach ($p in $j.PSObject.Properties) {
        $v = "$($p.Value)"
        if ($p.Name -match 'isk|ata|sl|older|ocation|ath' -or $v -match 'Docker|wsl|vhdx') {
            W ("{0} = {1}" -f $p.Name, $v)
        }
    }
}

W '=== any new/old vhdx on C: Docker dirs? ==='
Get-ChildItem "$env:LOCALAPPDATA\Docker" -Recurse -Filter *.vhdx -File -ErrorAction SilentlyContinue | ForEach-Object {
    W ("{0} = {1:N2} GB  modified {2}" -f $_.FullName, ($_.Length/1GB), $_.LastWriteTime.ToString('HH:mm:ss'))
}
Get-ChildItem "$env:LOCALAPPDATA\Docker\wsl" -Directory -ErrorAction SilentlyContinue | ForEach-Object { W ("dir: {0}" -f $_.FullName) }

W '=== backend log: mount/vhdx lines ==='
$logs = Get-ChildItem "$env:LOCALAPPDATA\Docker\log\host" -Filter *.log | Sort-Object LastWriteTime -Descending | Select-Object -First 3
foreach ($lg in $logs) {
    W ("--- {0} (last write {1}) ---" -f $lg.Name, $lg.LastWriteTime.ToString('HH:mm:ss'))
    Get-Content $lg.FullName -Tail 200 | Where-Object { $_ -match 'vhdx|docker_data|disk\b|DataFolder|DiskImage|mount|error|fail' } | Select-Object -Last 25 | ForEach-Object { W $_ }
}

W '=== current wsl distro state ==='
(& wsl -l -v) | ForEach-Object { $c = $_ -replace '[^\x20-\x7E]',''; if ($c -match '\S') { W $c } }

W '=== docker CLI check ==='
& docker version --format '{{.Server.Version}}' 2>&1 | ForEach-Object { W ("server version: {0}" -f $_) }
