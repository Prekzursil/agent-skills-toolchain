#Requires -Version 5.1
<#
.SYNOPSIS
  Bring up the minimal self-hosted, key-free search backend (TrailSearch) that
  powers search-hub's keyless selfhosted_* tools, on the Windows box.
.DESCRIPTION
  Reuses the estate SearXNG at host.docker.internal:8890 by default; pass
  -Bundled to also start a local SearXNG (UWSGI_WORKERS=1). No API keys are
  needed or set -- this is the keyless lane.
.EXAMPLE
  .\run-selfhosted-search.ps1 -Action up
  .\run-selfhosted-search.ps1 -Action up -Bundled
  .\run-selfhosted-search.ps1 -Action smoke
#>
param(
  [ValidateSet('up', 'down', 'smoke', 'logs')]
  [string]$Action = 'up',
  [switch]$Bundled
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

$Repo = if ($env:TRAILSEARCH_REPO) { $env:TRAILSEARCH_REPO } else { 'https://github.com/jianjungki/tavily-open.git' }
# Pinned to the ref measured for the 2026-09-02 decision record; bump deliberately.
$Ref = if ($env:TRAILSEARCH_REF) { $env:TRAILSEARCH_REF } else { 'e0e2dc1160fc60d0ea925e164194e34040e750f6' }
$env:TRAILSEARCH_SRC = if ($env:TRAILSEARCH_SRC) { $env:TRAILSEARCH_SRC } else { Join-Path $Here 'trailsearch-src' }
$Port = if ($env:SELFHOSTED_SEARCH_PORT) { $env:SELFHOSTED_SEARCH_PORT } else { '8794' }
$Compose = 'docker-compose.selfhosted-search.yml'
$ProfileArgs = @()
if ($Bundled) { $ProfileArgs = @('--profile', 'bundled') }

function Ensure-Src {
  if (-not (Test-Path (Join-Path $env:TRAILSEARCH_SRC '.git'))) {
    Write-Host "[run] cloning TrailSearch -> $($env:TRAILSEARCH_SRC)"
    git clone $Repo $env:TRAILSEARCH_SRC
  }
  Write-Host "[run] pinning TrailSearch @ $Ref"
  git -C $env:TRAILSEARCH_SRC fetch --quiet origin $Ref 2>$null
  git -C $env:TRAILSEARCH_SRC checkout --quiet $Ref
}

function Invoke-Smoke {
  Write-Host '[smoke] GET /docs'
  Invoke-RestMethod -Uri "http://127.0.0.1:$Port/docs" -Method Get | Out-Null
  Write-Host '  ok: healthy'
  Write-Host '[smoke] POST /tavily/search'
  $body = @{ query = 'self hosted search smoke'; max_results = 3; mode = 'search' } | ConvertTo-Json
  $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/tavily/search" -Method Post -ContentType 'application/json' -Body $body
  $r | ConvertTo-Json -Depth 4 | Select-Object -First 1
  Write-Host "[smoke] point the hub at it:  `$env:TRAILSEARCH_URL='http://127.0.0.1:$Port'"
}

switch ($Action) {
  'up' {
    Ensure-Src
    Write-Host "[run] docker compose up (app on 127.0.0.1:$Port)"
    docker compose -f $Compose @ProfileArgs up -d --build
    Write-Host '[run] waiting for /docs ...'
    for ($i = 0; $i -lt 60; $i++) {
      try { Invoke-RestMethod -Uri "http://127.0.0.1:$Port/docs" -Method Get | Out-Null; break }
      catch { Start-Sleep -Seconds 2 }
    }
    Invoke-Smoke
  }
  'down' { docker compose -f $Compose @ProfileArgs down }
  'logs' { docker compose -f $Compose @ProfileArgs logs -f }
  'smoke' { Invoke-Smoke }
}
