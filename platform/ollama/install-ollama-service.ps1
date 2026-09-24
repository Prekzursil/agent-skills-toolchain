<#
  Keep Ollama running so the semantic router keeps working.

  WHY: the router's index (595 rows) is built with nomic-embed-text via Ollama,
  and route.py embeds the live query the same way. If Ollama is down, routing
  silently degrades -- which is how the index sat stale from 2026-06-29 to
  2026-09-24 without anyone noticing: nothing ever failed loudly.

  Ollama is installed STANDALONE at D:\opt\ollama (winget's source database is
  corrupted on this box: 0x8a15000f). Models live on D: too, because C: is at
  90%.

      pwsh -File platform/ollama/install-ollama-service.ps1
      pwsh -File platform/ollama/install-ollama-service.ps1 -Uninstall
#>
[CmdletBinding(SupportsShouldProcess)]
param([switch]$Uninstall)

$ErrorActionPreference = 'Stop'

$Task   = 'ollama-serve'
$Exe    = 'D:\opt\ollama\ollama.exe'
$Models = 'D:\opt\ollama\models'

if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $Task -EA SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Task -Confirm:$false
        Write-Host "SUCCESS:uninstalled $Task"
    } else { Write-Host "NOT-PRESENT: $Task" }
    return
}

if (-not (Test-Path $Exe)) { throw "FAILED:install - ollama.exe not at $Exe" }

# Build the principal from the CURRENT identity rather than composing a
# domain\user string by hand. Hand-composing it produced
# 0x80070534 "no mapping between account names and security IDs".
$me = [Security.Principal.WindowsIdentity]::GetCurrent().Name
Write-Host "  principal: $me"

[Environment]::SetEnvironmentVariable('OLLAMA_MODELS', $Models, 'User')
[Environment]::SetEnvironmentVariable('OLLAMA_HOST', '127.0.0.1:11434', 'User')
New-Item -ItemType Directory -Force -Path $Models | Out-Null

$action  = New-ScheduledTaskAction -Execute $Exe -Argument 'serve'
$trigger = @(
    (New-ScheduledTaskTrigger -AtStartup),
    (New-ScheduledTaskTrigger -AtLogOn -User $me)
)
$principal = New-ScheduledTaskPrincipal -UserId $me -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
                -DontStopIfGoingOnBatteries -StartWhenAvailable `
                -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
                -ExecutionTimeLimit ([TimeSpan]::Zero)

if ($PSCmdlet.ShouldProcess($Task, 'Register-ScheduledTask')) {
    Register-ScheduledTask -TaskName $Task -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Force | Out-Null
}

$t = Get-ScheduledTask -TaskName $Task -EA SilentlyContinue
$listening = @(Get-NetTCPConnection -State Listen -LocalPort 11434 -EA SilentlyContinue).Count

Write-Host ("  task      : {0}" -f $(if ($t) { $t.State } else { 'NOT REGISTERED' }))
Write-Host ("  listening : {0} on 11434" -f $listening)

# Self-verify against the thing that actually matters: can the router embed?
try {
    $body = '{"model":"nomic-embed-text","input":"health"}'
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/embed' -Method Post `
            -Body $body -ContentType 'application/json' -TimeoutSec 20
    $dim = $r.embeddings[0].Count
    if ($dim -eq 768) { Write-Host "SUCCESS:ollama-service (embed dim=$dim)" }
    else { Write-Host "FAILED:ollama-service - unexpected embedding dim $dim" }
} catch {
    Write-Host "FAILED:ollama-service - embed probe failed: $($_.Exception.Message)"
    Write-Host "  if the model is missing:  D:\opt\ollama\ollama.exe pull nomic-embed-text"
}
