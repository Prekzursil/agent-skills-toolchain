$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $repoRoot 'config\codex-config-curated.toml'
$settingsPath = Join-Path $repoRoot 'config\vscode-chatgpt-supplement.json'
$envBundlePath = Join-Path $repoRoot 'env\private-env.windows.json'
python -c "import tomllib, pathlib; tomllib.loads(pathlib.Path(r'$configPath').read_text(encoding='utf-8-sig')); print('codex config parse ok')"
Get-Content $settingsPath -Raw | ConvertFrom-Json -Depth 20 | Out-Null
Write-Host 'VS Code supplement parse ok'
Get-Content $envBundlePath -Raw | ConvertFrom-Json -Depth 20 | Out-Null
Write-Host 'env bundle parse ok'
python -c "import requests; r=requests.get('http://127.0.0.1:47334/mcp/status', timeout=10); print('mindsdb status', r.status_code)"
node (Join-Path $repoRoot '..\..\editor\prompt-optimizer-button\scripts\smoke-test.js')
Write-Host 'workstation bundle validation passed'
