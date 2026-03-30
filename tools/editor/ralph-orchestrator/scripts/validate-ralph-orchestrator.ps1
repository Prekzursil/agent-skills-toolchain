param(
    [string]$WorkspaceRoot = "C:\Users\Prekzursil\source\agent-skills-toolchain",
    [string]$CodexConfigPath = "C:\Users\Prekzursil\.codex\config.toml",
    [string]$ClaudeServerName = "ralph-orchestrator",
    [string]$GeminiSettingsPath = "C:\Users\Prekzursil\.gemini\settings.json"
)

$ErrorActionPreference = "Stop"

function Invoke-GeminiMcpListProbe {
    param(
        [int]$TimeoutSeconds = 15,
        [string]$Pattern = "ralph-orchestrator"
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

foreach ($pathToCheck in @($WorkspaceRoot, $CodexConfigPath, $GeminiSettingsPath)) {
    if (-not (Test-Path $pathToCheck)) {
        throw "Missing required path: $pathToCheck"
    }
}

$ralphCommand = Get-Command ralph -ErrorAction SilentlyContinue
& wsl.exe -e bash -lc 'export PATH="$HOME/.local/bin:$PATH"; command -v ralph >/dev/null' *> $null
$wslHasRalph = ($LASTEXITCODE -eq 0)
if (-not $ralphCommand -and -not $wslHasRalph) {
    throw "ralph command not found on PATH or in WSL"
}

if ($ralphCommand) {
    & ralph --version | Out-Host
} else {
    & wsl.exe -e bash -lc 'export PATH="$HOME/.local/bin:$PATH"; ralph --version' | Out-Host
}

$codexCheck = @'
import pathlib
import tomllib
import sys

path = pathlib.Path(sys.argv[1])
data = tomllib.loads(path.read_text(encoding='utf-8-sig'))
server = data['mcp_servers']['ralph-orchestrator']
if server['command'] == 'ralph':
    assert server['args'] == ['mcp', 'serve']
else:
    assert server['command'].endswith('wsl.exe')
    assert server['args'] == ['-e', 'bash', '-lc', 'export PATH="$HOME/.local/bin:$PATH"; /home/prekzursil/.local/bin/ralph mcp serve']
assert server['enabled'] is True
print('codex config block ok')
'@
$codexCheck | & python - $CodexConfigPath | Out-Host
if ($LASTEXITCODE -ne 0) { throw "codex config validation failed" }

$geminiConfig = Get-Content -Raw $GeminiSettingsPath | ConvertFrom-Json -Depth 50
if (-not $geminiConfig.mcpServers.'ralph-orchestrator') {
    throw "Gemini ralph-orchestrator server missing"
}
$geminiCommand = $geminiConfig.mcpServers.'ralph-orchestrator'.command
$geminiArgs = @($geminiConfig.mcpServers.'ralph-orchestrator'.args)
if ($geminiCommand -eq "ralph") {
    if ($geminiArgs -join " " -ne "mcp serve") {
        throw "Gemini ralph-orchestrator server should use 'mcp serve'"
    }
} elseif ($geminiCommand -like "*wsl.exe") {
    if ($geminiArgs.Count -ne 4 -or $geminiArgs[0] -ne "-e" -or $geminiArgs[1] -ne "bash" -or $geminiArgs[2] -ne "-lc" -or $geminiArgs[3] -ne 'export PATH="$HOME/.local/bin:$PATH"; /home/prekzursil/.local/bin/ralph mcp serve') {
        throw "Gemini ralph-orchestrator server should use the expected WSL wrapper"
    }
} else {
    throw "Gemini ralph-orchestrator server should use either native ralph or the WSL wrapper"
}
Write-Host "gemini config block ok"

Push-Location $WorkspaceRoot
try {
    if ($wslHasRalph) {
        $doctorOutput = & wsl.exe -e bash -lc 'export PATH="$HOME/.local/bin:$PATH"; /home/prekzursil/.local/bin/ralph doctor' 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            throw "WSL ralph doctor failed"
        }
    } else {
        $doctorOutput = & ralph doctor 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            throw "ralph doctor failed"
        }
    }
    Write-Host $doctorOutput

    $claudeStatus = & claude mcp get $ClaudeServerName 2>&1 | Out-String
    $codexStatus = & codex mcp get $ClaudeServerName 2>&1 | Out-String
    $geminiProbe = Invoke-GeminiMcpListProbe -Pattern 'ralph-orchestrator'

    Write-Host $claudeStatus
    Write-Host $codexStatus
    if ($geminiProbe.TimedOut) {
        Write-Warning $geminiProbe.Output
    } elseif ($geminiProbe.Match) {
        Write-Host $geminiProbe.Match
    } else {
        Write-Warning "gemini mcp list completed but did not mention ralph-orchestrator"
        Write-Host $geminiProbe.Output
    }
} finally {
    Pop-Location
}

foreach ($agent in @("codex", "claude-code", "gemini-cli")) {
    $skillsJson = & npx skills ls -g -a $agent --json | ConvertFrom-Json -Depth 20
    foreach ($skillName in @("ralph-hats", "ralph-loop", "ralph-orchestrator-setup")) {
        if (-not ($skillsJson | Where-Object { $_.name -eq $skillName })) {
            throw "$skillName not installed for $agent"
        }
    }
}

Write-Host "skill install checks ok"
Write-Host "ralph validation completed"

