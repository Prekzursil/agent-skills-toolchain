param(
  [Parameter(Mandatory, Position=0)][ValidateSet('glm','claude','unified')][string]$ProfileName,
  [switch]$Force
)
$live = Get-Process claude -ErrorAction SilentlyContinue
if ($live -and -not $Force) {
  Write-Warning ("live claude TUI(s) PID {0} - saved settings hot-reload into running sessions. Flip between sessions, or rerun with -Force." -f ($live.Id -join ', '))
  exit 1
}
Import-Module "$env:USERPROFILE/.claude/profiles/cc-profiles.psm1" -Force
Invoke-CCProfile -Name $ProfileName
