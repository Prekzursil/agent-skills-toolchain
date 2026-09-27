# THROWAWAY test process for supervise.ps1's both-states proof. Touches nothing real.
#   -Mute          : stays ALIVE but stops heartbeating -> simulates a slow/mute daemon
#   -ExitAfterSec  : exits on its own -> simulates a crashing daemon
#   -MaxSec        : hard self-terminate. A test process must never outlive the test run.
param(
    [Parameter(Mandatory = $true)][string]$PidFile,
    [string]$HeartbeatFile,
    [switch]$Mute,
    [int]$ExitAfterSec = 0,
    [int]$MaxSec = 240
)
$ErrorActionPreference = 'SilentlyContinue'
Set-Content -LiteralPath $PidFile -Value ([string]$PID) -Encoding ascii
$t0 = Get-Date
while ($true) {
    if (-not $Mute -and $HeartbeatFile) {
        Set-Content -LiteralPath $HeartbeatFile -Value ((Get-Date).ToString('o')) -Encoding ascii
    }
    $el = ((Get-Date) - $t0).TotalSeconds
    if ($ExitAfterSec -gt 0 -and $el -ge $ExitAfterSec) { exit 0 }
    if ($el -ge $MaxSec) { exit 0 }
    Start-Sleep -Milliseconds 400
}
