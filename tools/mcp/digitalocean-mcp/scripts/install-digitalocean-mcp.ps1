param(
    [string]$CodexConfigPath = "C:\Users\Prekzursil\.codex\config.toml",
    [string]$ClaudeServerName = "digitalocean",
    [string]$GeminiSettingsPath = "C:\Users\Prekzursil\.gemini\settings.json",
    [string[]]$Services = @("apps")
)

$ErrorActionPreference = "Stop"

$serviceArgs = @("@digitalocean/mcp", "--services", ($Services -join ","))

function Assert-PathExists {
    param([string]$PathValue)
    if (-not (Test-Path $PathValue)) {
        throw "Missing required path: $PathValue"
    }
}

function Upsert-CodexServer {
    param([string]$TargetPath, [string]$ServerName, [string]$Command, [string[]]$ServerArgs)

    $argsToml = ($ServerArgs | ForEach-Object {
        '"' + ($_.Replace('\', '\\').Replace('"', '\"')) + '"'
    }) -join ", "

    $block = @"
[mcp_servers.$ServerName]
command = "$Command"
args = [$argsToml]
env_vars = ["DIGITALOCEAN_API_TOKEN"]
enabled = true
"@

    $content = Get-Content -Raw $TargetPath
    $pattern = '(?ms)^\[mcp_servers\.' + [regex]::Escape($ServerName) + '\]\r?\n.*?(?=^\[|\z)'
    if ([regex]::IsMatch($content, $pattern)) {
        $content = [regex]::Replace($content, $pattern, $block + "`r`n")
    } else {
        $content = $content.TrimEnd() + "`r`n`r`n" + $block + "`r`n"
    }
    Set-Content -Path $TargetPath -Value $content -Encoding UTF8
}

Assert-PathExists $CodexConfigPath
Assert-PathExists $GeminiSettingsPath

& npx @digitalocean/mcp --help | Out-Host

Upsert-CodexServer -TargetPath $CodexConfigPath -ServerName $ClaudeServerName -Command "npx" -ServerArgs $serviceArgs

$geminiConfig = Get-Content -Raw $GeminiSettingsPath | ConvertFrom-Json -Depth 50
if (-not $geminiConfig.mcpServers) {
    $geminiConfig | Add-Member -NotePropertyName "mcpServers" -NotePropertyValue ([pscustomobject]@{}) -Force
}
$geminiServer = [pscustomobject]@{
    command = "npx"
    args    = $serviceArgs
    env     = [pscustomobject]@{
        DIGITALOCEAN_API_TOKEN = '$DIGITALOCEAN_API_TOKEN'
    }
    trust   = $true
}
$geminiConfig.mcpServers | Add-Member -NotePropertyName $ClaudeServerName -NotePropertyValue $geminiServer -Force
$geminiConfig | ConvertTo-Json -Depth 50 | Set-Content -Path $GeminiSettingsPath -Encoding UTF8

& claude mcp remove -s user $ClaudeServerName *> $null
$claudeArgs = @("mcp", "add", "-s", "user", $ClaudeServerName, "--", "npx") + $serviceArgs
& claude @claudeArgs | Out-Host

Write-Host "Installed DigitalOcean MCP config for Codex, Claude, and Gemini"
Write-Host "Services: $($Services -join ', ')"
if (Get-ChildItem Env:DIGITALOCEAN_API_TOKEN -ErrorAction SilentlyContinue) {
    Write-Host "DIGITALOCEAN_API_TOKEN is present in the current session"
} else {
    Write-Warning "DIGITALOCEAN_API_TOKEN is not present in the current session; live connectivity remains env-gated"
}
