# bring-up.ps1 - start the full PentAGI stack (base + langfuse + graphiti + observability)
# Runs AFTER a working docker engine exists (local after nested-virt enablement,
# or any engine via DOCKER_HOST env override - e.g. a Linux docker host over
# Tailscale: $env:DOCKER_HOST="tcp://100.x.y.z:2375").
param(
    [switch]$BaseOnly,
    [switch]$PreflightOnly
)
$ErrorActionPreference = "Stop"
$Dir = $PSScriptRoot
$Docker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
$Compose = "C:\Program Files\Docker\Docker\resources\bin\docker-compose.exe"
if (-not (Test-Path $Docker)) { $Docker = "docker"; $Compose = "docker-compose" }

# Preflight: refuse to start while DOCKER_INSIDE is truthy in .env.
# DOCKER_INSIDE=true mounts the Docker engine socket into every agent sandbox;
# on this box the engine runs in the Docker Desktop WSL2 VM which shares C:\ and
# D:\, so a downloaded binary can walk sandbox -> socket -> engine root ->
# WSL2 VM -> Windows drives. See HARDENING.md.
function Get-DockerInsideValue {
    param([Parameter(Mandatory = $true)][string]$EnvFile)
    if (-not (Test-Path -LiteralPath $EnvFile)) { throw "preflight: .env not found at $EnvFile" }
    $value = $null
    foreach ($line in Get-Content -LiteralPath $EnvFile) {
        $t = $line.Trim()
        if ($t.StartsWith("#") -or $t.StartsWith(";") -or -not $t.Contains("=")) { continue }
        $key, $raw = $t -split "=", 2
        if ($key.Trim() -eq "DOCKER_INSIDE") {
            # last assignment wins (compose env-file semantics); strip inline comment
            $value = (($raw -split "\s+#", 2)[0]).Trim().Trim('"').Trim("'")
        }
    }
    if ([string]::IsNullOrWhiteSpace($value)) { $value = "false" } # compose default
    return $value
}
$dockerInside = Get-DockerInsideValue -EnvFile (Join-Path $Dir ".env")
if ($dockerInside -match "^(?i)(1|t|true)$") {
    throw ("Refusing to start: DOCKER_INSIDE={0} in {1}\.env mounts the Docker socket into every agent sandbox (sandbox -> socket -> WSL2 VM -> C:\ escape chain; see HARDENING.md). Set DOCKER_INSIDE=false or use the commented two-node / remote-engine alternative." -f $dockerInside, $Dir)
}
Write-Host "preflight OK: DOCKER_INSIDE=$dockerInside (socket not mounted into agent sandboxes)"
if ($PreflightOnly) { Write-Host "preflight-only run - stopping before docker/compose."; return }

Write-Host "waiting for docker engine (DOCKER_HOST=$env:DOCKER_HOST)..."
$deadline = (Get-Date).AddMinutes(10)
while ($true) {
    & $Docker info *> $null
    if ($LASTEXITCODE -eq 0) { break }
    if ((Get-Date) -gt $deadline) { throw "docker engine not reachable after 10 minutes" }
    Start-Sleep -Seconds 5
}
Write-Host "engine OK. pulling + starting base stack (this pulls several GB on first run)..."
& $Compose --env-file "$Dir\.env" -f "$Dir\docker-compose.yml" up -d --pull missing

if (-not $BaseOnly) {
    Write-Host "starting supplementary stacks..."
    & $Compose --env-file "$Dir\.env" -f "$Dir\docker-compose.yml" -f "$Dir\docker-compose-langfuse.yml" up -d --pull missing
    & $Compose --env-file "$Dir\.env" -f "$Dir\docker-compose.yml" -f "$Dir\docker-compose-graphiti.yml" up -d --pull missing
    & $Compose --env-file "$Dir\.env" -f "$Dir\docker-compose.yml" -f "$Dir\docker-compose-observability.yml" up -d --pull missing
}

Write-Host ""
Write-Host "PentAGI:      https://localhost:8443  (login admin@pentagi.com / admin - CHANGE IMMEDIATELY)"
Write-Host "Langfuse:     http://localhost:3000  (create project, put keys into .env LANGFUSE_PUBLIC_KEY/SECRET_KEY)"
Write-Host "Grafana:      http://localhost:3001  (observability dashboards)"
Write-Host "Neo4j/Graphiti knowledge graph enabled (GRAPHITI_ENABLED=true)."
& $Docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
