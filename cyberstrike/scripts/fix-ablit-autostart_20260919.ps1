# Idempotent autostart wiring for glm-hosted-retry proxy (127.0.0.1:18319)
$ErrorActionPreference = 'Continue'

# 1. Report any existing scheduled-task autostart
$tasks = Get-ScheduledTask | Where-Object { $_.TaskName -match 'glm|ablit|18319|gateway' }
if ($tasks) { $tasks | Select-Object TaskName, State | Format-Table -AutoSize | Out-String | Write-Output }
else { Write-Output "SCHEDULED_TASKS: none match glm/ablit/18319/gateway" }

# 2. Ensure HKCU Run key (idempotent)
$run = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$name = 'glm-hosted-retry'
$cmd  = 'powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "D:\bolt\tools\glm-hosted-retry\start.ps1"'
$existing = (Get-ItemProperty -Path $run -Name $name -ErrorAction SilentlyContinue).$name
if ($existing -eq $cmd) {
  Write-Output "RUN_KEY: already correct"
} else {
  New-ItemProperty -Path $run -Name $name -Value $cmd -PropertyType String -Force | Out-Null
  Write-Output "RUN_KEY: written"
}

# 3. Verify readback
$back = (Get-ItemProperty -Path $run -Name $name -ErrorAction SilentlyContinue).$name
Write-Output ("RUN_KEY_READBACK: " + $(if ($back -eq $cmd) { 'OK' } else { 'MISMATCH: ' + $back }))
