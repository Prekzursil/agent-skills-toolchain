# bm - one-command dispatcher for the local Biomni stack (WSL2 gradio UI, :7860).
#   bm open     ensure up (readiness-poll, not a blind sleep) then open the UI
#   bm ensure   headless ensure-up for tools/agents -> SUCCESS:bm-up / FAILED:bm-down
#   bm status   [-Json] state incl. measured latency + wedged flag
#   bm fix      graceful force-recover (stop -> clear stale locks -> restart)
#   bm stop     stop the daemon
#   bm task "<prompt>"  run an A1 agent task (GLM coding plan); result saved + shown
#   bm tool <cmd...>    any E1 CLI tool (plink2, bwa, iqtree2, muscle, homer...)
#   bm r '<R code>'     R one-liner inside the biomni_e1 env
#   bm doctor  full-stack PASS/WARN/FAIL report    |   bm help
# ASCII-only on purpose (bm.cmd invokes this under Windows PowerShell 5.1).
[CmdletBinding()]
param(
  [Parameter(Position = 0)][string]$Verb = 'help',
  [Parameter(Position = 1, ValueFromRemainingArguments = $true)][string[]]$Rest,
  [switch]$Json
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bm-lib.ps1')

function Write-BMInfo { param([string]$Message) Write-Information -MessageData $Message -InformationAction Continue }

function Invoke-BMEnsureUp {
  $h = Test-BMHealth
  switch ($h.State) {
    'HEALTHY' { return $true }
    'SLOW'    { Write-BMInfo "wedged ($($h.Ms)ms) -> recover"; [void](Invoke-BMWsl 'bm-recover' 75) }
    'DOWN'    { Write-BMInfo 'down -> start'; [void](Invoke-BMWsl 'bm-start' 45) }
  }
  return (Wait-BMAlive 150)
}

switch ($Verb.ToLower()) {
  'ensure' {
    # THE PRECONDITION CONTRACT: terminal-state marker on stdout only (progress -> info stream).
    $ok = Invoke-BMEnsureUp
    if ($Json) {
      $hh = Test-BMHealth
      [pscustomobject]@{ ok = $ok; marker = $(if ($ok) { 'SUCCESS:bm-up' } else { 'FAILED:bm-down' }); state = $hh.State; http_status = $hh.Http; latency_ms = $hh.Ms; url = $script:BMUrl } | ConvertTo-Json -Compress
    } else {
      Write-Output $(if ($ok) { 'SUCCESS:bm-up' } else { 'FAILED:bm-down' })
    }
    if ($ok) { exit 0 } else { exit 1 }
  }
  'open' {
    if (Invoke-BMEnsureUp) {
      Start-Process $script:BMUrl
      Write-BMInfo "opened $($script:BMUrl)"
    } else { Write-Warning 'Biomni did not come up; run: bm doctor'; exit 1 }
  }
  'status' {
    $h = Test-BMHealth
    $procs = Format-BMProbeReply (Invoke-BMWsl 'bm-health' 15)
    if ($Json) {
      [pscustomobject]@{ running = ($h.State -ne 'DOWN'); wedged = ($h.State -eq 'SLOW'); http_status = $h.Http; latency_ms = $h.Ms; url = $script:BMUrl; wsl = $procs } | ConvertTo-Json -Compress
    } else {
      $state = if ($h.State -eq 'HEALTHY') { 'HEALTHY' } elseif ($h.State -eq 'SLOW') { '*** WEDGED ***' } else { 'DOWN' }
      "state  : {0} (http {1}, {2}ms)" -f $state, $h.Http, $h.Ms
      "url    : {0}" -f $script:BMUrl
      "wsl    : {0}" -f $procs
    }
  }
  'fix'   { Write-Output (Invoke-BMWsl 'bm-recover' 75) }
  'stop'  { Write-Output (Invoke-BMWsl 'bm-stop' 20) }
  'tool'  {
    if (-not $Rest) { Write-Warning 'usage: bm tool <command> [args]'; exit 1 }
    $cmd = $Rest -join ' '
    Write-Output (Invoke-BMWsl "export PATH=/home/prekzursil/Biomni/biomni_env/biomni_tools/bin:/home/prekzursil/Biomni/biomni_env/biomni_tools/homer/bin:`$PATH; $cmd" 60)
  }
  'r'     {
    if (-not $Rest) { Write-Warning "usage: bm r '<R code>'"; exit 1 }
    $code = $Rest -join ' '
    Write-Output (Invoke-BMWsl "export PATH=/home/prekzursil/miniforge3/envs/biomni_e1/bin:`$PATH; Rscript -e '$code'" 60)
  }
  'task'  {
    if (-not $Rest) { Write-Warning 'usage: bm task "<prompt>"'; exit 1 }
    $prompt = ($Rest -join ' ') -replace '"', '\"'
    $tasksDir = Get-BMSetting 'BM_TASKS_DIR' 'D:\Research\tools\biomni-local\tasks'
    New-Item -ItemType Directory -Force -Path $tasksDir | Out-Null
    $ts = Get-Date -Format 'yyyyMMdd-HHmmss'
    $wslPy = "/tmp/bm_task_$ts.py"
    $winOut = Join-Path $tasksDir "task_$ts.out"
    # Canonical A1 construction (bare A1() asserts - load_dotenv + explicit kwargs).
    $pyLines = @(
      'import os'
      'from pathlib import Path'
      'from dotenv import load_dotenv'
      'load_dotenv("/home/prekzursil/Biomni/.env")'
      'tools_bin = os.path.expanduser("~/Biomni/biomni_env/biomni_tools/bin")'
      'os.environ["PATH"] = tools_bin + ":" + os.environ.get("PATH", "")'
      'from biomni.agent import A1'
      'agent = A1(path=str(Path.home() / "Biomni" / "data"), llm=os.environ["BIOMNI_LLM"], source="Custom", base_url=os.environ["BIOMNI_CUSTOM_BASE_URL"], api_key=os.environ["BIOMNI_CUSTOM_API_KEY"])'
      'r = agent.go("""' + $prompt + '""")'
      'print("BM-TASK-RESULT-BEGIN")'
      'print(r[1] if isinstance(r, tuple) else r)'
      'print("BM-TASK-RESULT-END")'
    )
    $py = ($pyLines -join "`n") -replace "`r", ''
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($py)
    # write via WSL base64 (immune to every quoting layer)
    $b64 = [Convert]::ToBase64String($bytes)
    $wr = Invoke-BMWsl "echo $b64 | base64 -d > $wslPy; test -s $wslPy && echo WRITTEN" 45
    if ($wr -notmatch 'WRITTEN') {
      Write-Output "FAILED:bm-task script write did not verify ($wr)"
      exit 1
    }
    Write-Output (Invoke-BMWsl "/home/prekzursil/bin/biomni $wslPy 2>&1 | tail -n +1" 600) | Tee-Object -FilePath $winOut
    Write-BMInfo "saved: $winOut"
  }
  'doctor' {
    if ($Json) { & (Join-Path $PSScriptRoot 'bm-doctor.ps1') -Json } else { & (Join-Path $PSScriptRoot 'bm-doctor.ps1') }
    exit $LASTEXITCODE
  }
  default {
    @'
bm - Biomni (local) control - the cs pattern
  bm open               ensure up (readiness poll) + open the web UI (:7860)
  bm ensure             headless ensure-up -> SUCCESS:bm-up / FAILED:bm-down
  bm status [-Json]     state incl. latency + wedged flag
  bm fix                graceful force-recover         bm stop   stop the daemon
  bm task "<prompt>"    A1 agent task on the GLM plan; saved to D:\Research\tools\biomni-local\tasks
  bm tool <cmd> [args]  any E1 CLI tool               bm r '<R code>'  R one-liner
  bm doctor             full-stack PASS/WARN/FAIL/NOT-CHECKED report; exits non-zero on FAIL
A slow/timeout response = WEDGED (WSL frozen, usually host-RAM). NOT-CHECKED is not PASS.
Config: bm.conf next to this script. Slash command: /biomni.
'@
  }
}
