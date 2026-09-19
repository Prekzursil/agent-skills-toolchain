$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

# Safety: capture current registration state before touching anything
$key = (Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' | Where-Object { (Get-ItemProperty $_.PSPath).DistributionName -eq 'Ubuntu' })
$props = Get-ItemProperty $key.PSPath
Write-Output ("PRE-MOVE: Name={0} DefaultUid={1} Version={2} BasePath={3}" -f $props.DistributionName, $props.DefaultUid, $props.Version, $props.BasePath)
$uid = $props.DefaultUid

# Terminate just Ubuntu (leave docker-desktop alone)
& wsl --terminate Ubuntu
Start-Sleep -Seconds 3

# Create parent only -- the move target itself must not exist
New-Item -ItemType Directory -Path 'D:\WSL' -Force | Out-Null
if (Test-Path 'D:\WSL\Ubuntu') { Write-Output 'ERROR: D:\WSL\Ubuntu already exists - aborting'; exit 1 }

$freeC = (Get-PSDrive C).Free
Write-Output ("C: free before move: {0:N1} GB" -f ($freeC/1GB))
Write-Output 'Starting: wsl --manage Ubuntu --move D:\WSL\Ubuntu'

$proc = Start-Process -FilePath 'wsl.exe' -ArgumentList '--manage','Ubuntu','--move','D:\WSL\Ubuntu' -NoNewWindow -PassThru -RedirectStandardOutput "$env:USERPROFILE\.agents\wsl_move_out.log" -RedirectStandardError "$env:USERPROFILE\.agents\wsl_move_err.log"
Write-Output ("Move process PID {0} launched at {1}" -f $proc.Id, (Get-Date -Format 'HH:mm:ss'))
$proc.WaitForExit()
Write-Output ("Move process exited code {0} at {1}" -f $proc.ExitCode, (Get-Date -Format 'HH:mm:ss'))

# Verify
$p2 = Get-ItemProperty $key.PSPath
Write-Output ("POST-MOVE: BasePath={0}" -f $p2.BasePath)
Get-ChildItem 'D:\WSL\Ubuntu' -Filter *.vhdx -File -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Output ("New vhdx: {0} = {1:N2} GB" -f $_.FullName, ($_.Length/1GB))
}
$freeC2 = (Get-PSDrive C).Free
Write-Output ("C: free after move: {0:N1} GB  (reclaimed {1:N1} GB)" -f ($freeC2/1GB), (($freeC2-$freeC)/1GB))

# Functional check
$out = & wsl -d Ubuntu -u root -e sh -c 'echo WSL_OK; df -h / | tail -1; ls /home'
foreach ($l in $out) { $clean = $l -replace '[^\x20-\x7E]',''; if ($clean -match '\S') { Write-Output $clean } }
# restore default user if the uid changed (paranoia)
if ($p2.DefaultUid -ne $uid) {
    Set-ItemProperty -Path $key.PSPath -Name DefaultUid -Value $uid
    Write-Output ("DefaultUid restored to {0}" -f $uid)
}
