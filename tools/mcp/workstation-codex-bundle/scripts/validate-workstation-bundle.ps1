$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $repoRoot 'config\codex-config-curated.toml'
$manifestPath = Join-Path $repoRoot 'bundle.manifest.json'
$settingsPath = Join-Path $repoRoot 'config\vscode-chatgpt-supplement.json'
$envBundlePath = Join-Path $repoRoot 'env\private-env.windows.json'

$codexConfigCheck = @'
import pathlib
import tomllib

path = pathlib.Path(r"__CONFIG_PATH__")
data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
mcp = data.get("mcp_servers", {})

assert "cheatengine" in mcp, "cheatengine MCP should be present"
assert "github_cli" in mcp, "github_cli MCP should be present"
assert "semgrep" in mcp, "semgrep MCP should be present"
assert "codecov" in mcp, "codecov MCP should be present"
assert "deepsource" in mcp, "deepsource MCP should be present"
assert "digitalocean" in mcp, "digitalocean MCP should be present"
assert "ralph-orchestrator" in mcp, "ralph-orchestrator MCP should be present"
assert "deepscan" not in mcp, "deepscan should not remain in the active config snapshot"
assert "qlty" not in mcp, "qlty should not remain in the active config snapshot"
assert "mindsdb" not in mcp, "mindsdb should not remain in the current config snapshot"
assert "desktop-commander" not in mcp, "desktop-commander should not remain in the current config snapshot"

semgrep = mcp["semgrep"]
assert semgrep.get("command") == "C:/Users/Prekzursil/.local/bin/uvx.exe", "semgrep MCP should run through uvx"
assert semgrep.get("args", [None])[0] == "semgrep-mcp", "semgrep MCP should use the semgrep-mcp wrapper"

codecov = mcp["codecov"]
assert codecov.get("env_vars") == ["CODECOV_BASE_URL", "CODECOV_TOKEN"], "codecov MCP should use CODECOV_BASE_URL + CODECOV_TOKEN"

deepsource = mcp["deepsource"]
assert deepsource.get("command") == "C:\\Program Files\\nodejs\\node.exe", "deepsource MCP should run through the local Node wrapper"
assert "deepsource-mcp-wrapper.mjs" in deepsource.get("args", [""])[0], "deepsource MCP should point at the local wrapper"

sentry = mcp.get("sentry", {})
assert "OPENAI_API_KEY" not in sentry.get("env_vars", []), "OPENAI_API_KEY should not remain in sentry env"

notion = mcp.get("notion", {})
assert notion.get("url") == "https://mcp.notion.com/mcp", "Notion should target /mcp"

cheat = mcp["cheatengine"]
assert "mcp_cheatengine.py" in cheat["args"][0], "Cheat Engine should point at the upstream Python bridge"

digitalocean = mcp["digitalocean"]
assert digitalocean.get("command") == "npx", "DigitalOcean MCP should use npx"
assert digitalocean.get("args") == ["@digitalocean/mcp", "--services", "apps"], "DigitalOcean MCP should stay on the archived App Platform package"
assert digitalocean.get("env_vars") == ["DIGITALOCEAN_API_TOKEN"], "DigitalOcean MCP should use env-only token wiring"

ralph = mcp["ralph-orchestrator"]
assert ralph.get("command") == "C:/Windows/System32/wsl.exe", "Ralph MCP should use the WSL launcher on this workstation"
assert ralph.get("args") == ["-e", "bash", "-lc", "export PATH=\"$HOME/.local/bin:$PATH\"; /home/prekzursil/.local/bin/ralph mcp serve"], "Ralph MCP should run through the expected WSL wrapper"

print("codex config parse ok")
'@
$codexConfigCheck = $codexConfigCheck.Replace("__CONFIG_PATH__", $configPath)
$codexConfigCheck | python - | Out-Host

$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json -Depth 20
$nonMcpIds = @($manifest.core_bundle.curated_non_mcp | ForEach-Object { $_.id })
if ($nonMcpIds -contains 'codecov') { throw 'Codecov should no longer be classified as non-MCP' }
if (-not ($nonMcpIds -contains 'chromatic')) { throw 'Chromatic should remain in curated_non_mcp' }
foreach ($fallback in 'deepscan', 'qlty') {
    if (-not ($nonMcpIds -contains $fallback)) { throw "$fallback should be tracked in curated_non_mcp as a supported fallback" }
}
$optionalIds = @($manifest.optional_extras | ForEach-Object { $_.id })
if (-not ($optionalIds -contains 'codecov')) { throw 'Codecov should be tracked in optional_extras after MCP promotion' }
if (-not ($optionalIds -contains 'deepsource')) { throw 'DeepSource should be tracked in optional_extras after wrapper promotion' }
$coreIds = @($manifest.core_bundle.curated_upstream | ForEach-Object { $_.id })
if (-not ($coreIds -contains 'semgrep')) { throw 'Semgrep should be tracked in core_bundle.curated_upstream' }
$blockedIds = @($manifest.staged_or_disabled | ForEach-Object { $_.id })
foreach ($blocked in 'deepscan', 'qlty') {
    if ($blockedIds -contains $blocked) { throw "$blocked should no longer be tracked in staged_or_disabled once the fallback workflow is documented" }
}
Write-Host 'bundle manifest parse ok'

$settings = Get-Content $settingsPath -Raw | ConvertFrom-Json -Depth 20
if ($settings.'codecov.api.url' -ne 'https://api.codecov.io') { throw 'VS Code supplement should target https://api.codecov.io' }
if ($settings.'codecov.coverage.enabled' -ne $false) { throw 'VS Code supplement should set codecov.coverage.enabled=false' }
Write-Host 'VS Code supplement parse ok'

$envBundle = Get-Content $envBundlePath -Raw | ConvertFrom-Json -Depth 20
$vars = $envBundle.variables
if ($vars.PSObject.Properties.Name -contains 'UNITY_MCP_REPO') { throw 'UNITY_MCP_REPO should not remain in env bundle' }
if (-not ($vars.PSObject.Properties.Name -contains 'CHROMATIC_PROJECT_TOKEN')) { throw 'CHROMATIC_PROJECT_TOKEN should be present in env bundle' }
if (-not ($vars.PSObject.Properties.Name -contains 'CODECOV_BASE_URL')) { throw 'CODECOV_BASE_URL should be present in env bundle' }
if (-not ($vars.PSObject.Properties.Name -contains 'CODECOV_TOKEN')) { throw 'CODECOV_TOKEN should be present in env bundle' }
if (-not ($vars.PSObject.Properties.Name -contains 'DEEPSOURCE_API_KEY')) { throw 'DEEPSOURCE_API_KEY should be present in env bundle for the local DeepSource wrapper' }
Write-Host 'env bundle parse ok'

& 'C:\Windows\System32\wsl.exe' -e bash -lc 'export PATH="$HOME/.local/bin:$PATH"; ralph --version' | Select-Object -First 1 | Out-Host

$cheatEngineInstall = 'C:\Program Files\Cheat Engine\autorun\zz_ce_mcp_bridge.lua'
if (Test-Path $cheatEngineInstall) {
    Write-Host 'cheatengine autorun wrapper present'
} else {
    Write-Warning 'cheatengine autorun wrapper not present on this machine'
}

& 'D:\Tools\codecov-cli\.venv\Scripts\codecovcli.exe' --help | Select-Object -First 1 | Out-Host
if (-not (Test-Path (Join-Path $repoRoot 'scripts\deepsource-mcp-wrapper.mjs'))) { throw 'Repo-owned DeepSource wrapper source missing' }
if (-not (Test-Path 'C:\Users\Prekzursil\.local\opt\deepsource-mcp-server\deepsource-mcp-wrapper.mjs')) { throw 'DeepSource wrapper script missing' }
if (-not (Test-Path 'D:\Tools\chromatic-playwright\package.json')) { throw 'Chromatic workspace package.json missing' }
Write-Host 'chromatic workspace present'
Write-Host 'workstation bundle validation passed'
