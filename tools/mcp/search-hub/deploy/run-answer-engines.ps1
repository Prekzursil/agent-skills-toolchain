#Requires -Version 5.1
<#
.SYNOPSIS
  Start / stop the OPT-IN, ON-DEMAND answer engines behind search-hub's `answer`
  lane on the Windows box: Vane (selfhosted_answer) and local-deep-research (its web
  UI + REST API; the hub's LDR MCP path, ENABLE_LDR=1, runs ldr-mcp over STDIO on
  the host).
.DESCRIPTION
  Nothing starts unless a profile switch is given (-Vane / -Ldr / -Ollama) -- 0 RAM
  idle is the default. Reuses the estate SearXNG at host.docker.internal:8890 and
  the host Ollama at host.docker.internal:11434; override with the env vars listed
  in env.minimal.example. -Print shows the resolved env and the exact compose
  command WITHOUT running Docker. No API keys are needed or set.
  Bash twin: run-answer-engines.sh (same flags as --vane / --ldr / --ollama / --print).
.EXAMPLE
  .\run-answer-engines.ps1 -Action up -Vane
  .\run-answer-engines.ps1 -Action up -Vane -Ldr -Print
  .\run-answer-engines.ps1 -Action down          # every profile
  .\run-answer-engines.ps1 -Action smoke -Vane
#>
param(
  [ValidateSet('up', 'down', 'logs', 'ps', 'smoke', 'print')]
  [string]$Action = 'up',
  [switch]$Vane,
  [switch]$Ldr,
  [switch]$Ollama,
  [switch]$Print
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here
$Compose = 'docker-compose.answer-engines.yml'

function Resolve-Env([string]$Name, [string]$Default) {
  $v = [Environment]::GetEnvironmentVariable($Name)
  if ([string]::IsNullOrWhiteSpace($v)) { $v = $Default }
  [Environment]::SetEnvironmentVariable($Name, $v)
  return $v
}

# Pins verified 2026-09-02 (Docker Hub + upstream tags); bump deliberately, and
# re-read Vane's /api/providers + /api/search contract if you move off v1.12.2.
$VaneImage = Resolve-Env 'VANE_IMAGE' 'itzcrazykns1337/vane:slim-v1.12.2'
$VanePort = Resolve-Env 'VANE_PORT' '3000'
$VaneSearxng = Resolve-Env 'VANE_SEARXNG_API_URL' 'http://host.docker.internal:8890'
$VaneOllama = Resolve-Env 'VANE_OLLAMA_BASE_URL' 'http://host.docker.internal:11434'
$VaneMem = Resolve-Env 'VANE_MEM_LIMIT' '768m'
$LdrImage = Resolve-Env 'LDR_IMAGE' 'localdeepresearch/local-deep-research:1.10.7'
$LdrPort = Resolve-Env 'LDR_PORT' '5000'
$LdrOllama = Resolve-Env 'LDR_OLLAMA_URL' 'http://host.docker.internal:11434'
$LdrSearxng = Resolve-Env 'LDR_SEARXNG_URL' 'http://host.docker.internal:8890'
$LdrMem = Resolve-Env 'LDR_MEM_LIMIT' '2g'
$OllamaImage = Resolve-Env 'OLLAMA_IMAGE' 'ollama/ollama:0.33.2'
$OllamaPort = Resolve-Env 'OLLAMA_PORT' '11434'
$OllamaMem = Resolve-Env 'OLLAMA_MEM_LIMIT' '16g'
$Restart = Resolve-Env 'ANSWER_ENGINES_RESTART' 'no'
# The eviction policy the `ollama` profile hard-codes; set the same on a host Ollama
# (setx OLLAMA_KEEP_ALIVE 0, then restart Ollama).
$OllamaKeepAlive = '0'

if ($Print) { $Action = 'print' }   # --print wins over any action: never reaches Docker

# down/logs/ps with no switch mean every profile (compose skips profiled services
# it is not told about, which would leave containers running after a down).
if (($Action -in @('down', 'logs', 'ps')) -and -not ($Vane -or $Ldr -or $Ollama)) {
  $Vane = $true; $Ldr = $true; $Ollama = $true
}

$ProfileArgs = @()
$ProfileNames = @()
if ($Vane) { $ProfileArgs += @('--profile', 'vane'); $ProfileNames += 'vane' }
if ($Ldr) { $ProfileArgs += @('--profile', 'ldr'); $ProfileNames += 'ldr' }
if ($Ollama) { $ProfileArgs += @('--profile', 'ollama'); $ProfileNames += 'ollama' }

function Compose-Cmd([string]$Verb) {
  return "docker compose -f $Compose $($ProfileArgs -join ' ') $Verb"
}

function Show-Env {
  $names = if ($ProfileNames.Count) { $ProfileNames -join ' ' } else { '<none -- pass -Vane / -Ldr / -Ollama>' }
  Write-Output '# answer-engines: resolved env (nothing was started; Docker not invoked)'
  Write-Output "# profiles: $names"
  Write-Output "COMPOSE_FILE=$(Join-Path $Here $Compose)"
  Write-Output "ANSWER_ENGINES_RESTART=$Restart"
  Write-Output "VANE_IMAGE=$VaneImage"
  Write-Output "VANE_PORT=$VanePort"
  Write-Output "VANE_SEARXNG_API_URL=$VaneSearxng"
  Write-Output "VANE_OLLAMA_BASE_URL=$VaneOllama"
  Write-Output "VANE_MEM_LIMIT=$VaneMem"
  Write-Output "LDR_IMAGE=$LdrImage"
  Write-Output "LDR_PORT=$LdrPort"
  Write-Output "LDR_OLLAMA_URL=$LdrOllama"
  Write-Output "LDR_SEARXNG_URL=$LdrSearxng"
  Write-Output "LDR_MEM_LIMIT=$LdrMem"
  Write-Output "OLLAMA_IMAGE=$OllamaImage"
  Write-Output "OLLAMA_PORT=$OllamaPort"
  Write-Output "OLLAMA_MEM_LIMIT=$OllamaMem"
  Write-Output "OLLAMA_KEEP_ALIVE=$OllamaKeepAlive   # hard-coded in the ollama profile; set it on a host Ollama too"
  Write-Output '# would run:'
  Write-Output "#   $(Compose-Cmd 'up -d')"
  Write-Output "#   $(Compose-Cmd 'down')"
  Write-Output '# then point the hub at the engines (endpoint-agnostic: an OVH URL works the same):'
  Write-Output "#   `$env:ENABLE_VANE='1'; `$env:VANE_URL='http://127.0.0.1:$VanePort'    # or VANE_URL=https://vane.your.ovh"
  Write-Output '#   VANE_TIMEOUT_S=120 is the LLM budget per answer (raise for slow models)'
  Write-Output "#   `$env:ENABLE_LDR='1'       # LDR MCP ProviderSpec (providers.py): runs ldr-mcp over STDIO via uvx on the host"
  Write-Output "#   LDR web UI + REST API from -Ldr: http://127.0.0.1:$LdrPort   # NOT LDR_URL: providers.py uses LDR_URL only"
  Write-Output '#                                                             # for a resident ldr-mcp behind a Streamable-HTTP gateway'
}

function Invoke-Smoke {
  if ($Vane) {
    Write-Host '[smoke] vane GET /api/providers'
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:$VanePort/api/providers" -Method Get
    Write-Host "  providers: $(@($r.providers).Count)"
    Write-Host "[smoke] point the hub at it:  `$env:ENABLE_VANE='1'; `$env:VANE_URL='http://127.0.0.1:$VanePort'"
  }
  if ($Ldr) {
    Write-Host '[smoke] ldr GET /api/v1/health'
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:$LdrPort/api/v1/health" -Method Get
    Write-Host "  status: $($r.status)"
    Write-Host "[smoke] LDR web UI + REST API: http://127.0.0.1:$LdrPort  (hub MCP path is separate:"
    Write-Host "[smoke]   `$env:ENABLE_LDR='1' runs ldr-mcp over STDIO on the host; LDR_URL is NOT this port)"
  }
  if ($Ollama) {
    Write-Host '[smoke] ollama GET /api/tags'
    Invoke-RestMethod -Uri "http://127.0.0.1:$OllamaPort/api/tags" -Method Get | Out-Null
    Write-Host '  ok: daemon answers (OLLAMA_KEEP_ALIVE=0 -> models evicted after each answer)'
  }
}

function Wait-For([string]$Url) {
  for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-RestMethod -Uri $Url -Method Get | Out-Null; return }
    catch { Start-Sleep -Seconds 2 }
  }
  Write-Warning "$Url did not answer within 120 s (first pull can take longer)"
}

switch ($Action) {
  'print' { Show-Env }
  'up' {
    if ($ProfileArgs.Count -eq 0) {
      Write-Error 'refusing: nothing is started by default -- pass -Vane and/or -Ldr (and -Ollama only without a host Ollama)'
      exit 2
    }
    Write-Host "[run] $(Compose-Cmd 'up -d')"
    docker compose -f $Compose @ProfileArgs up -d
    if ($Vane) { Wait-For "http://127.0.0.1:$VanePort/api/providers" }
    if ($Ldr) { Wait-For "http://127.0.0.1:$LdrPort/api/v1/health" }
    Invoke-Smoke
  }
  'down' {
    Write-Host "[run] $(Compose-Cmd 'down')"
    docker compose -f $Compose @ProfileArgs down
  }
  'logs' { docker compose -f $Compose @ProfileArgs logs -f }
  'ps' { docker compose -f $Compose @ProfileArgs ps }
  'smoke' {
    if (-not ($Vane -or $Ldr -or $Ollama)) { $Vane = $true; $Ldr = $true }
    Invoke-Smoke
  }
}
