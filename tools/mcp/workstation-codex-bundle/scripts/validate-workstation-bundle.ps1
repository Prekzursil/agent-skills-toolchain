$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $repoRoot 'config\codex-config-curated.toml'
$settingsPath = Join-Path $repoRoot 'config\vscode-chatgpt-supplement.json'
$envBundlePath = Join-Path $repoRoot 'env\private-env.windows.json'

python -c "import pathlib, tomllib; data=tomllib.loads(pathlib.Path(r'$configPath').read_text(encoding='utf-8-sig')); assert 'terraform' not in data.get('mcp_servers', {}), 'terraform should be removed'; assert 'unity' not in data.get('mcp_servers', {}), 'unity should be removed'; sentry=data['mcp_servers'].get('sentry', {}); assert 'OPENAI_API_KEY' not in sentry.get('env_vars', []), 'OPENAI_API_KEY should not remain in sentry env'; notion=data['mcp_servers'].get('notion', {}); assert notion.get('url') == 'https://mcp.notion.com/mcp', 'Notion should target /mcp'; print('codex config parse ok')"

$settings = Get-Content $settingsPath -Raw | ConvertFrom-Json -Depth 20
if ($settings.'codecov.api.url' -ne 'https://api.codecov.io') { throw 'VS Code supplement should target https://api.codecov.io' }
if ($settings.'codecov.coverage.enabled' -ne $false) { throw 'VS Code supplement should set codecov.coverage.enabled=false' }
Write-Host 'VS Code supplement parse ok'

$envBundle = Get-Content $envBundlePath -Raw | ConvertFrom-Json -Depth 20
$vars = $envBundle.variables
if ($vars.PSObject.Properties.Name -contains 'UNITY_MCP_REPO') { throw 'UNITY_MCP_REPO should not remain in env bundle' }
if (-not ($vars.PSObject.Properties.Name -contains 'CHROMATIC_PROJECT_TOKEN')) { throw 'CHROMATIC_PROJECT_TOKEN should be present in env bundle' }
Write-Host 'env bundle parse ok'

python -c "import requests; r=requests.get('http://127.0.0.1:47334/mcp/status', timeout=10); print('mindsdb status', r.status_code)"
& 'D:\Tools\codecov-cli\.venv\Scripts\codecovcli.exe' --help | Select-Object -First 1 | Out-Host
if (-not (Test-Path 'D:\Tools\chromatic-playwright\package.json')) { throw 'Chromatic workspace package.json missing' }
Write-Host 'chromatic workspace present'
node (Join-Path $repoRoot '..\..\editor\prompt-optimizer-button\scripts\smoke-test.js')
Write-Host 'workstation bundle validation passed'
