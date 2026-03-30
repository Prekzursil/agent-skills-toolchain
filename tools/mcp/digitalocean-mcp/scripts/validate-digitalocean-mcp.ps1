param(
    [string]$CodexConfigPath = "C:\Users\Prekzursil\.codex\config.toml",
    [string]$ClaudeServerName = "digitalocean",
    [string]$GeminiSettingsPath = "C:\Users\Prekzursil\.gemini\settings.json"
)

$ErrorActionPreference = "Stop"

function Invoke-GeminiMcpListProbe {
    param(
        [int]$TimeoutSeconds = 15,
        [string]$Pattern = "digitalocean"
    )

    $job = Start-Job -ScriptBlock { gemini mcp list 2>&1 | Out-String }
    try {
        if (-not (Wait-Job $job -Timeout $TimeoutSeconds)) {
            Stop-Job $job -ErrorAction SilentlyContinue
            return [pscustomobject]@{
                TimedOut = $true
                Output   = "gemini mcp list timed out after $TimeoutSeconds seconds"
            }
        }

        $output = Receive-Job $job | Out-String
        $match = ($output | Select-String -Pattern $Pattern -CaseSensitive:$false | Out-String).Trim()
        return [pscustomobject]@{
            TimedOut = $false
            Output   = $output
            Match    = $match
        }
    } finally {
        Remove-Job $job -Force -ErrorAction SilentlyContinue
    }
}

foreach ($pathToCheck in @($CodexConfigPath, $GeminiSettingsPath)) {
    if (-not (Test-Path $pathToCheck)) {
        throw "Missing required path: $pathToCheck"
    }
}

& npx @digitalocean/mcp --help | Out-Host

$codexCheck = @'
import pathlib
import tomllib
import sys

path = pathlib.Path(sys.argv[1])
data = tomllib.loads(path.read_text(encoding='utf-8-sig'))
server = data['mcp_servers']['digitalocean']
assert server['command'] == 'npx'
assert server['args'] == ['@digitalocean/mcp', '--services', 'apps']
assert server['env_vars'] == ['DIGITALOCEAN_API_TOKEN']
assert server['enabled'] is True
print('codex config block ok')
'@
$codexCheck | & python - $CodexConfigPath | Out-Host
if ($LASTEXITCODE -ne 0) { throw "codex config validation failed" }

$geminiConfig = Get-Content -Raw $GeminiSettingsPath | ConvertFrom-Json -Depth 50
if (-not $geminiConfig.mcpServers.digitalocean) {
    throw "Gemini digitalocean server missing"
}
if ($geminiConfig.mcpServers.digitalocean.command -ne "npx") {
    throw "Gemini digitalocean server should use npx"
}
if ((@($geminiConfig.mcpServers.digitalocean.args) -join " ") -ne "@digitalocean/mcp --services apps") {
    throw "Gemini digitalocean server should use the expected archived package args"
}
if ($geminiConfig.mcpServers.digitalocean.env.DIGITALOCEAN_API_TOKEN -ne '$DIGITALOCEAN_API_TOKEN') {
    throw "Gemini digitalocean server should keep the token as an env reference"
}
Write-Host "gemini config block ok"

$claudeStatus = & claude mcp get $ClaudeServerName 2>&1 | Out-String
Write-Host $claudeStatus

$codexStatus = & codex mcp get $ClaudeServerName 2>&1 | Out-String
Write-Host $codexStatus

$geminiProbe = Invoke-GeminiMcpListProbe -Pattern 'digitalocean'
if ($geminiProbe.TimedOut) {
    Write-Warning $geminiProbe.Output
} elseif ($geminiProbe.Match) {
    Write-Host $geminiProbe.Match
} else {
    Write-Warning "gemini mcp list completed but did not mention digitalocean"
    Write-Host $geminiProbe.Output
}

if (Get-ChildItem Env:DIGITALOCEAN_API_TOKEN -ErrorAction SilentlyContinue) {
    Write-Host "DIGITALOCEAN_API_TOKEN present in current session"
} else {
    Write-Warning "DIGITALOCEAN_API_TOKEN missing; live DigitalOcean connectivity remains env-gated"
}

Write-Host "digitalocean validation completed"

