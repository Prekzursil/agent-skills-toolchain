# READINESS probe for the supervise.ps1 self-test. Implements the documented exit contract:
#   0 = READY   1 = SELF-FAULT (restartable)   2 = DEPENDENCY   3 = WARMUP   other = UNKNOWN
param(
    [string]$HeartbeatFile,
    [int]$MaxAgeSec = 4,
    [int]$StaleAs = 2,
    [string]$ForceExit
)
$ErrorActionPreference = 'SilentlyContinue'
if ($ForceExit) { exit ([int]$ForceExit) }
if (-not $HeartbeatFile -or -not (Test-Path -LiteralPath $HeartbeatFile)) { exit $StaleAs }
$age = ((Get-Date) - (Get-Item -LiteralPath $HeartbeatFile).LastWriteTime).TotalSeconds
if ($age -le $MaxAgeSec) { exit 0 }
exit $StaleAs
