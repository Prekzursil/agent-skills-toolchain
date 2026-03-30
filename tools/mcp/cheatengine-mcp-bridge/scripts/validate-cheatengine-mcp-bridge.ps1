param(
    [string]$InstallRoot = "C:\Users\Prekzursil\.local\opt\cheatengine-mcp-bridge",
    [string]$CodexConfigPath = "C:\Users\Prekzursil\.codex\config.toml",
    [switch]$RequireLivePipe
)

$ErrorActionPreference = 'Stop'
$venvPython = Join-Path $InstallRoot '.venv\Scripts\python.exe'
$bridgePython = Join-Path $InstallRoot 'MCP_Server\mcp_cheatengine.py'
$bridgeLua = Join-Path $InstallRoot 'MCP_Server\ce_mcp_bridge.lua'
$autorunWrapper = 'C:\Program Files\Cheat Engine\autorun\zz_ce_mcp_bridge.lua'
$logPath = Join-Path $InstallRoot 'autorun-bootstrap.log'

foreach ($path in @($venvPython, $bridgePython, $bridgeLua, $autorunWrapper, $CodexConfigPath)) {
    if (-not (Test-Path $path)) { throw "Missing required path: $path" }
}

& $venvPython -c "import importlib.util; assert importlib.util.find_spec('mcp'); assert importlib.util.find_spec('win32file'); assert importlib.util.find_spec('anyio'); print('python deps ok')"
python -c "import pathlib, tomllib; data=tomllib.loads(pathlib.Path(r'$CodexConfigPath').read_text(encoding='utf-8-sig')); srv=data['mcp_servers']['cheatengine']; assert srv['enabled'] is True; assert 'mcp_cheatengine.py' in srv['args'][0]; print('config block ok')"

if (Test-Path $logPath) {
    Write-Host 'autorun log present'
}

if ($RequireLivePipe) {
    $env:PYTHONPATH = Join-Path $InstallRoot 'MCP_Server'
    & $venvPython -c "import mcp_cheatengine; print(mcp_cheatengine.ce_client.send_command('ping'))"
}
