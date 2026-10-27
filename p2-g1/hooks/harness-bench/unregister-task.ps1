<#
  unregister-task.ps1 - remove the ClaudeHarnessBench weekly Scheduled Task registered by
  register-task.ps1. Leaves baseline.json in place (delete it manually to reset the bar).

  EXACT command this script runs:
    schtasks /Delete /TN "ClaudeHarnessBench" /F
#>
$ErrorActionPreference = 'Stop'

schtasks /Delete /TN "ClaudeHarnessBench" /F
