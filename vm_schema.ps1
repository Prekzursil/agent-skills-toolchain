$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
function W($m) { Write-Output ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }

W '=== ALL settings-store.json keys ==='
$j = Get-Content "$env:APPDATA\Docker\settings-store.json" -Raw | ConvertFrom-Json
$j.PSObject.Properties | ForEach-Object { W ("{0} = {1}" -f $_.Name, ("$($_.Value)" -replace '\s+',' ').Substring(0, [Math]::Min(90, ("$($_.Value)").Length))) }

W '=== other Docker config files ==='
Get-ChildItem "$env:APPDATA\Docker" -File | ForEach-Object { W ("{0}  {1:N0} KB  {2}" -f $_.Name, ($_.Length/1KB), $_.LastWriteTime.ToString('HH:mm:ss')) }

W '=== docker desktop CLI? ==='
& docker desktop --help 2>&1 | Select-Object -First 30 | ForEach-Object { W $_ }

$exe = 'C:\Program Files\Docker\Docker\resources\com.docker.backend.exe'
$enc = [Text.Encoding]::GetEncoding('ISO-8859-1')
$txt = [IO.File]::ReadAllText($exe, $enc)

W '=== contexts: docker_data.vhdx ==='
$idx = 0; $hits = 0
while (($idx = $txt.IndexOf('docker_data.vhdx', $idx)) -ge 0 -and $hits -lt 5) {
    $start = [Math]::Max(0, $idx - 120); $len = [Math]::Min(260, $txt.Length - $start)
    W ("...{0}..." -f (($txt.Substring($start, $len)) -replace '[^\x20-\x7E]','.'))
    $idx += 16; $hits++
}

W '=== contexts: json:"dataFolder" ==='
$idx = 0; $hits = 0
while (($idx = $txt.IndexOf('json:"dataFolder', $idx)) -ge 0 -and $hits -lt 5) {
    $start = [Math]::Max(0, $idx - 140); $len = [Math]::Min(280, $txt.Length - $start)
    W ("...{0}..." -f (($txt.Substring($start, $len)) -replace '[^\x20-\x7E]','.'))
    $idx += 17; $hits++
}

W '=== contexts: WslDataFolder json tag forms ==='
foreach ($t in @('json:"wslDataFolder"','json:"vm.resources.wslDataFolder"')) {
    $idx = $txt.IndexOf($t)
    if ($idx -ge 0) {
        $start = [Math]::Max(0, $idx - 160); $len = [Math]::Min(320, $txt.Length - $start)
        W ("{0}: ...{1}..." -f $t, (($txt.Substring($start, $len)) -replace '[^\x20-\x7E]','.'))
    } else { W ("{0}: NOT FOUND" -f $t) }
}
