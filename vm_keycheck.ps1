$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
function W($m) { Write-Output ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }

W '=== context around WslDataFolder in backend binary ==='
$exe = 'C:\Program Files\Docker\Docker\resources\com.docker.backend.exe'
$enc = [Text.Encoding]::GetEncoding('ISO-8859-1')
$txt = [IO.File]::ReadAllText($exe, $enc)
$idx = 0; $hits = 0
while (($idx = $txt.IndexOf('WslDataFolder', $idx)) -ge 0 -and $hits -lt 6) {
    $start = [Math]::Max(0, $idx - 60); $len = [Math]::Min(160, $txt.Length - $start)
    $chunk = $txt.Substring($start, $len) -replace '[^\x20-\x7E]','.'
    W ("hit {0}: ...{1}..." -f $hits, $chunk)
    $idx += 14; $hits++
}
W '--- json tag check ---'
foreach ($tag in @('json:"WslDataFolder"','json:"DataFolder"','json:"DiskImageLocation"')) {
    W ("{0} present: {1}" -f $tag, $txt.Contains($tag))
}
W '--- default path strings near WslDataFolder usage ---'
foreach ($s in @('wsl\disk\docker_data.vhdx','/disk/docker_data.vhdx','AppData\Local\Docker\wsl')) {
    W ("'{0}' present: {1}" -f $s, $txt.Contains($s))
}
W ''
W '=== is the D: vhdx actually in use right now? ==='
Get-Item 'D:\Docker\wsl\disk\docker_data.vhdx' | ForEach-Object { W ("D: vhdx modified {0}, size {1:N2} GB" -f $_.LastWriteTime.ToString('HH:mm:ss'), ($_.Length/1GB)) }
Get-Item 'C:\Users\Prekzursil\AppData\Local\Docker\wsl\disk\docker_data.vhdx' | ForEach-Object { W ("C: vhdx modified {0}, size {1:N2} GB" -f $_.LastWriteTime.ToString('HH:mm:ss'), ($_.Length/1GB)) }
W '--- volumes/containers (fresh disk would be empty of user data) ---'
& docker volume ls --format '{{.Name}}' 2>&1 | ForEach-Object { W ("vol: {0}" -f $_) }
& docker ps -a --format '{{.Names}}  {{.Image}}  {{.Status}}' 2>&1 | ForEach-Object { W ("ctr: {0}" -f $_) }
& docker system df 2>&1 | ForEach-Object { W ("df: {0}" -f $_) }
