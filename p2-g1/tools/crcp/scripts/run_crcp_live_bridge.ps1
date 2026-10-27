param(
    [int]$HttpPort = 8820,
    [int]$PollInterval = 60
)
$ErrorActionPreference = "Continue"
$CrpRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $CrpRoot "crcp\__main__.py"))) {
  $CrpRoot = "C:\Users\Prekzursil\source\agent-skills-toolchain\tools\crcp"
}
$env:PYTHONPATH = $CrpRoot
$env:NO_PROXY = "127.0.0.1,localhost"
$env:no_proxy = "127.0.0.1,localhost"
$env:HTTP_PROXY = ""; $env:HTTPS_PROXY = ""; $env:http_proxy = ""; $env:https_proxy = ""
$LogDir = Join-Path $CrpRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "crcp_live_bridge.log"
function Log($m) { $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m; Add-Content $LogFile $line -Encoding utf8; Write-Host $line }
Log "START live bridge root=$CrpRoot port=$HttpPort poll=$PollInterval py=$(Get-Command python | Select-Object -Expand Source)"
$py = (Get-Command python).Source
# Run without piping so exit codes work
$p = Start-Process -FilePath $py -ArgumentList @("-m","crcp","chatgpt","live","--poll-interval","$PollInterval","--http-port","$HttpPort") -WorkingDirectory $CrpRoot -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $LogDir "crcp_live_stdout.log") -RedirectStandardError (Join-Path $LogDir "crcp_live_stderr.log")
Log "spawned pid=$($p.Id)"
# Wait forever; task restarts if we exit
Wait-Process -Id $p.Id
$code = $p.ExitCode
Log "EXIT child=$code"
exit $(if ($null -eq $code) { 1 } else { $code })
