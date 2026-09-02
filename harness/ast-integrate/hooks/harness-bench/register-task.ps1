#Requires -Version 5.1
<#
  register-task.ps1 - register the harness-bench regression net as a WEEKLY Windows
  Scheduled Task named 'ClaudeHarnessBench' (low frequency: it is a regression net, not a
  real-time monitor). The task runs bench.py, which runs `eval.py --json`, compares the
  shipped HYBRID router's recall to baseline.json, and appends ONE background-digest line
  on a drop. Runs as the current user; no admin required. Unregister: unregister-task.ps1.

  EXACT command this script runs (paths resolved at run time):
    schtasks /Create /TN "ClaudeHarnessBench" /TR "\"<python>\" \"<dir>\bench.py\"" /SC WEEKLY /D SUN /ST 03:00 /F
#>
$ErrorActionPreference = 'Stop'

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $python) { Write-Error 'No python/py found on PATH; install Python or add it to PATH.'; exit 1 }

$bench = Join-Path $PSScriptRoot 'bench.py'
if (-not (Test-Path $bench)) { Write-Error "bench.py not found at $bench"; exit 1 }

# schtasks stores the /TR string verbatim; each path is double-quoted so spaces survive.
$run = '"{0}" "{1}"' -f $python, $bench
Write-Host "Registering ClaudeHarnessBench -> $run"

schtasks /Create /TN "ClaudeHarnessBench" /TR $run /SC WEEKLY /D SUN /ST 03:00 /F
