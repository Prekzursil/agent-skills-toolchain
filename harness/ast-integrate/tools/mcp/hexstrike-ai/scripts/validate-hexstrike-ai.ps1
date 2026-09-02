param(
    [string]$InstallRoot = "C:\Users\Prekzursil\.local\opt\hexstrike-ai",
    [string]$CodexConfigPath = "C:\Users\Prekzursil\.codex\config.toml",
    [string]$ClaudeServerName = "hexstrike-ai",
    [string]$GeminiSettingsPath = "C:\Users\Prekzursil\.gemini\settings.json"
)

$ErrorActionPreference = 'Stop'

$venvPython = Join-Path $InstallRoot '.venv\Scripts\python.exe'
$launcherPath = Join-Path $InstallRoot 'hexstrike_mcp_launcher.py'
$healthUrl = 'http://127.0.0.1:8888/health'

foreach ($path in @(
    (Join-Path $InstallRoot 'hexstrike_server.py'),
    (Join-Path $InstallRoot 'hexstrike_mcp.py'),
    $venvPython,
    $launcherPath,
    $CodexConfigPath,
    $GeminiSettingsPath
)) {
    if (-not (Test-Path $path)) { throw "Missing required path: $path" }
}

& $venvPython -c "import importlib.util; assert importlib.util.find_spec('flask'); assert importlib.util.find_spec('requests'); assert importlib.util.find_spec('mcp'); print('python deps ok')"

python -c "import pathlib, tomllib; data=tomllib.loads(pathlib.Path(r'$CodexConfigPath').read_text(encoding='utf-8-sig')); srv=data['mcp_servers']['hexstrike-ai']; assert srv['enabled'] is True; assert 'hexstrike_mcp_launcher.py' in srv['args'][0]; print('codex config block ok')"

$gemini = Get-Content $GeminiSettingsPath -Raw | ConvertFrom-Json -Depth 20
if (-not $gemini.mcpServers.'hexstrike-ai') { throw 'Gemini hexstrike-ai server missing' }
if ($gemini.mcpServers.'hexstrike-ai'.args[0] -notlike '*hexstrike_mcp_launcher.py') { throw 'Gemini hexstrike-ai server should point at the launcher' }
Write-Host 'gemini config block ok'

$response = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 60
$payload = $response.Content | ConvertFrom-Json
if ($payload.status -ne 'healthy') { throw "HexStrike health endpoint returned unexpected status: $($payload.status)" }
Write-Host 'hexstrike health ok'

$claudeStatus = & claude mcp get $ClaudeServerName 2>&1 | Out-String
$codexStatus = & codex mcp get $ClaudeServerName 2>&1 | Out-String
$geminiStatus = & gemini mcp list 2>&1 | Out-String

Write-Host $claudeStatus
Write-Host $codexStatus
Write-Host ($geminiStatus | Select-String -Pattern 'hexstrike-ai' -CaseSensitive:$false | Out-String)

if ($claudeStatus -match 'Failed to connect') {
    Write-Warning 'Claude HexStrike MCP is configured but still failing direct health checks.'
}
if ($geminiStatus -match 'hexstrike-ai:.*Disconnected') {
    Write-Warning 'Gemini HexStrike MCP is configured but still failing direct health checks.'
}

Write-Host 'hexstrike validation completed'
