$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$vhdx = 'C:\Users\Prekzursil\AppData\Local\Packages\CanonicalGroupLimited.Ubuntu_79rhkp1fndgsc\LocalState\ext4.vhdx'

Write-Output 'Terminating Ubuntu...'
& wsl --terminate Ubuntu 2>&1 | Out-Null

Write-Output 'Waiting for vhdx lock release...'
$unlocked = $false
for ($i = 1; $i -le 60; $i++) {
    try {
        $fs = [IO.File]::Open($vhdx, 'Open', 'Read', 'None')
        $fs.Close(); $fs.Dispose()
        $unlocked = $true
        Write-Output ("unlocked after {0} tries ({1}s)" -f $i, $i)
        break
    } catch { Start-Sleep -Seconds 1 }
}
if (-not $unlocked) { Write-Output 'FAILED: vhdx still locked after 60s - listing wsl state'; & wsl -l -v; exit 1 }

$freeC = (Get-PSDrive C).Free
Write-Output ("C: free before move: {0:N1} GB" -f ($freeC/1GB))
Write-Output ("Move started {0}" -f (Get-Date -Format 'HH:mm:ss'))

& wsl --manage Ubuntu --move D:\WSL\Ubuntu 2>&1 | Out-File "$env:USERPROFILE\.agents\wsl_move2.log" -Encoding Unicode
Write-Output ("Move command returned {0} at {1}" -f $LASTEXITCODE, (Get-Date -Format 'HH:mm:ss'))

$mv = [Text.Encoding]::Unicode.GetString([IO.File]::ReadAllBytes("$env:USERPROFILE\.agents\wsl_move2.log")) -replace '[^\x20-\x7E\r\n]',''
Write-Output ("Move output: {0}" -f $mv.Trim())

$key = (Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' | Where-Object { (Get-ItemProperty $_.PSPath).DistributionName -eq 'Ubuntu' })
$p2 = Get-ItemProperty $key.PSPath
Write-Output ("POST-MOVE BasePath: {0}" -f $p2.BasePath)
Get-ChildItem 'D:\WSL\Ubuntu' -Filter *.vhdx -File -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Output ("New vhdx on D:: {0} = {1:N2} GB" -f $_.Name, ($_.Length/1GB))
}
$freeC2 = (Get-PSDrive C).Free
Write-Output ("C: free after move: {0:N1} GB  (reclaimed {1:N1} GB)" -f ($freeC2/1GB), (($freeC2-$freeC)/1GB))

if ($p2.BasePath -like 'D:*') {
    Write-Output 'Setting vhdx sparse for auto-trim...'
    & wsl --manage Ubuntu --set-sparse true 2>&1 | Out-File "$env:USERPROFILE\.agents\wsl_sparse.log" -Encoding Unicode
    $sp = [Text.Encoding]::Unicode.GetString([IO.File]::ReadAllBytes("$env:USERPROFILE\.agents\wsl_sparse.log")) -replace '[^\x20-\x7E\r\n]',''
    Write-Output ("Sparse output: {0}" -f $sp.Trim())
    & wsl --terminate Ubuntu 2>&1 | Out-Null
    Start-Sleep -Seconds 5
    Get-ChildItem 'D:\WSL\Ubuntu' -Filter *.vhdx -File | ForEach-Object {
        Write-Output ("vhdx after sparse: {0:N2} GB" -f ($_.Length/1GB))
    }
    # functional check
    $out = & wsl -d Ubuntu -e sh -c 'echo WSL_OK; whoami; df -h / | tail -1'
    foreach ($l in $out) { $clean = $l -replace '[^\x20-\x7E]',''; if ($clean -match '\S') { Write-Output $clean } }
}
