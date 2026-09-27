# Firecrawl stack health watchdog (2026-09-22, owner directive)
# ROOT CAUSE this guards: the self-hosted firecrawl docker stack
# (D:\opt\firecrawl) had RestartPolicy=no, so any Docker Desktop
# restart silently killed it and every firecrawl MCP tool failed with a
# bare "Tool execution failed". Layers already in place:
#   - docker update --restart unless-stopped  (set 2026-09-22 on all 7)
#   - "Docker Desktop" shortcut in the user Startup folder
# This task is layer 3: if the stack is ever down while Docker runs,
# bring it back up and log it.
# Log: C:\Users\Prekzursil\.agents\logs\firecrawl-mcp-health.jsonl
$ErrorActionPreference = 'Continue'

$containers = @('firecrawl-api-1', 'firecrawl-nuq-worker-1',
                'firecrawl-playwright-service-1', 'firecrawl-rabbitmq-1',
                'firecrawl-redis-1', 'firecrawl-nuq-postgres-1',
                'firecrawl-foundationdb-1')
$logDir = 'C:\Users\Prekzursil\.agents\logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory $logDir | Out-Null }
$logPath = Join-Path $logDir 'firecrawl-mcp-health.jsonl'
$ts = (Get-Date).ToUniversalTime().ToString('o')

$down = @()
foreach ($c in $containers) {
    $running = docker inspect -f '{{.State.Running}}' $c 2>$null
    if ($running -ne 'true') { $down += $c }
}

$action = 'none'
if ($down.Count -gt 0) {
    # start docker engine first if it is not running at all
    $dockerUp = Get-Process 'com.docker.backend' -ErrorAction SilentlyContinue
    if (-not $dockerUp) {
        Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
        $deadline = (Get-Date).AddSeconds(90)
        while (-not $dockerUp -and (Get-Date) -lt $deadline) {
            Start-Sleep 5
            $dockerUp = Get-Process 'com.docker.backend' -ErrorAction SilentlyContinue
        }
    }
    foreach ($c in $down) { docker start $c 2>$null | Out-Null }
    $action = "started: $($down -join ', ')"
}

$entry = @{ ts = $ts; down = $down.Count; action = $action } |
    ConvertTo-Json -Compress
Add-Content -Path $logPath -Value $entry
Write-Output "down=$($down.Count) action=$action"
