param(
    [ValidateSet("auto", "registry", "vendored", "cargo", "wsl-release")]
    [string]$InstallSource = "auto",
    [string]$Version = "2.8.1",
    [string]$CodexConfigPath = "C:\Users\Prekzursil\.codex\config.toml",
    [string]$ClaudeServerName = "ralph-orchestrator",
    [string]$GeminiSettingsPath = "C:\Users\Prekzursil\.gemini\settings.json",
    [string]$SkillRepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")).Path,
    [string]$WslInstallRoot = "/home/prekzursil/.local/opt/ralph-orchestrator",
    [string]$WslRalphPath = "/home/prekzursil/.local/bin/ralph",
    [string]$WindowsShimDir = "C:\Users\Prekzursil\.local\bin",
    [switch]$SkipSkillInstall
)

$ErrorActionPreference = "Stop"

$toolRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$vendoredSnapshotPath = Join-Path $toolRoot "vendor"
$windowsWslCommand = "C:/Windows/System32/wsl.exe"
$wslLaunchArg = 'export PATH="$HOME/.local/bin:$PATH"; /home/prekzursil/.local/bin/ralph mcp serve'

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$ScriptBlock,
        [Parameter(Mandatory = $true)]
        [string]$ErrorMessage
    )

    $global:LASTEXITCODE = 0
    & $ScriptBlock
    if ($LASTEXITCODE -ne 0) {
        throw $ErrorMessage
    }
}

function Invoke-PythonFileUpdate {
    param(
        [string]$TargetPath,
        [string]$ServerName,
        [string]$ServerCommand,
        [string[]]$ServerArgs
    )

    $pythonCode = @'
import json
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
server_name = sys.argv[2]
server_command = sys.argv[3]
server_args = json.loads(sys.argv[4])
args_repr = ", ".join(json.dumps(arg) for arg in server_args)
block = f'[mcp_servers."{server_name}"]\ncommand = {json.dumps(server_command)}\nargs = [{args_repr}]\nenabled = true\n'
text = path.read_text(encoding="utf-8-sig")
pattern = re.compile(rf'(?ms)^\[mcp_servers\."{re.escape(server_name)}"\]\r?\n.*?(?=^\[|\Z)')

if pattern.search(text):
    text = pattern.sub(block + "\n", text)
else:
    text = text.rstrip() + "\n\n" + block

path.write_text(text, encoding="utf-8")
'@

    $serverArgsJson = $ServerArgs | ConvertTo-Json -Compress
    $pythonCode | & python - $TargetPath $ServerName $ServerCommand $serverArgsJson
}

function Ensure-RalphCli {
    $effectiveSource = $InstallSource
    if ($effectiveSource -eq "auto") {
        if ($env:OS -eq "Windows_NT") {
            $effectiveSource = "wsl-release"
        } else {
            $effectiveSource = "registry"
        }
    }

    switch ($effectiveSource) {
        "registry" {
            Invoke-Checked -ScriptBlock { npm install -g "@ralph-orchestrator/ralph-cli@$Version" } -ErrorMessage "npm install for Ralph failed"
            break
        }
        "vendored" {
            if (-not (Test-Path $vendoredSnapshotPath)) {
                throw "Vendored Ralph snapshot missing at $vendoredSnapshotPath"
            }
            Invoke-Checked -ScriptBlock { npm install -g $vendoredSnapshotPath } -ErrorMessage "vendored npm install for Ralph failed"
            break
        }
        "cargo" {
            Invoke-Checked -ScriptBlock { cargo install ralph-cli --version $Version --force } -ErrorMessage "cargo install for Ralph failed"
            break
        }
        "wsl-release" {
            $downloadPath = Join-Path $env:TEMP "ralph-cli-x86_64-unknown-linux-gnu.tar.xz"
            Invoke-Checked -ScriptBlock {
                Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/mikeyobrien/ralph-orchestrator/releases/download/v$Version/ralph-cli-x86_64-unknown-linux-gnu.tar.xz" -OutFile $downloadPath
            } -ErrorMessage "Downloading the Ralph Linux tarball failed"

            $wslArchivePath = "/mnt/c/Users/Prekzursil/Temp/ralph-cli-x86_64-unknown-linux-gnu.tar.xz"
            $extractCommand = @'
set -euo pipefail
mkdir -p "__INSTALL_ROOT__"
rm -rf "__INSTALL_ROOT__/ralph-cli-x86_64-unknown-linux-gnu"
tar -xJf "__ARCHIVE_PATH__" -C "__INSTALL_ROOT__"
mkdir -p "$HOME/.local/bin"
ln -sf "__INSTALL_ROOT__/ralph-cli-x86_64-unknown-linux-gnu/ralph" "__RALPH_PATH__"
cat > "$HOME/.local/bin/claude" <<'EOF'
#!/usr/bin/env bash
exec /mnt/c/Users/Prekzursil/.local/bin/claude.exe "$@"
EOF
cat > "$HOME/.local/bin/gemini" <<'EOF'
#!/usr/bin/env bash
exec /mnt/c/Windows/System32/cmd.exe /c C:\\Users\\Prekzursil\\.local\\bin\\gemini.cmd "$@"
EOF
chmod +x "$HOME/.local/bin/claude" "$HOME/.local/bin/gemini"
'@
            $extractCommand = $extractCommand.Replace("__INSTALL_ROOT__", $WslInstallRoot).Replace("__ARCHIVE_PATH__", $wslArchivePath).Replace("__RALPH_PATH__", $WslRalphPath)
            Invoke-Checked -ScriptBlock {
                wsl.exe -e bash -lc $extractCommand
            } -ErrorMessage "Installing the Ralph Linux tarball inside WSL failed"

            New-Item -ItemType Directory -Force -Path $WindowsShimDir | Out-Null
            $cmdWrapper = @'
@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0ralph.ps1" %*
'@
            Set-Content -Path (Join-Path $WindowsShimDir "ralph.cmd") -Encoding ASCII -Value $cmdWrapper
            $psWrapper = @'
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ForwardArgs
)

$joined = [string]::Join(' ', ($ForwardArgs | ForEach-Object { $_.Replace('"', '\"') }))
$bashCommand = 'export PATH="$HOME/.local/bin:$PATH"; __RALPH_PATH__'
if ($joined) {
    $bashCommand += " $joined"
}
& 'C:\Windows\System32\wsl.exe' -e bash -lc $bashCommand
exit $LASTEXITCODE
'@
            $psWrapper = $psWrapper.Replace("__RALPH_PATH__", $WslRalphPath)
            Set-Content -Path (Join-Path $WindowsShimDir "ralph.ps1") -Encoding UTF8 -Value $psWrapper
            & npm uninstall -g @ralph-orchestrator/ralph-cli *> $null
            break
        }
    }

    return $effectiveSource
}

function Get-ServerCommandSpec {
    param([string]$EffectiveSource)

    if ($EffectiveSource -eq "wsl-release") {
        return @{
            command = $windowsWslCommand
            args    = @("-e", "bash", "-lc", $wslLaunchArg)
        }
    }

    return @{
        command = "ralph"
        args    = @("mcp", "serve")
    }
}

function Assert-RalphAvailable {
    param([string]$EffectiveSource)

    if ($EffectiveSource -eq "wsl-release") {
        Invoke-Checked -ScriptBlock {
            wsl.exe -e bash -lc 'export PATH="$HOME/.local/bin:$PATH"; command -v ralph >/dev/null && ralph --version'
        } -ErrorMessage "WSL Ralph verification failed"
        return
    }

    $ralphCommand = Get-Command ralph -ErrorAction SilentlyContinue
    if (-not $ralphCommand) {
        throw "ralph command not found after install"
    }

    & ralph --version | Out-Host
}

function Assert-PathExists {
    param([string]$PathValue)
    if (-not (Test-Path $PathValue)) {
        throw "Missing required path: $PathValue"
    }
}

$effectiveSource = Ensure-RalphCli
Assert-RalphAvailable -EffectiveSource $effectiveSource
$serverSpec = Get-ServerCommandSpec -EffectiveSource $effectiveSource

Assert-PathExists $CodexConfigPath
Invoke-PythonFileUpdate -TargetPath $CodexConfigPath -ServerName $ClaudeServerName -ServerCommand $serverSpec.command -ServerArgs $serverSpec.args

Assert-PathExists $GeminiSettingsPath
$geminiConfig = Get-Content -Raw $GeminiSettingsPath | ConvertFrom-Json -Depth 50
if (-not $geminiConfig.mcpServers) {
    $geminiConfig | Add-Member -NotePropertyName "mcpServers" -NotePropertyValue ([pscustomobject]@{}) -Force
}
$geminiServer = [pscustomobject]@{
    command = $serverSpec.command
    args    = $serverSpec.args
    trust   = $true
}
$geminiConfig.mcpServers | Add-Member -NotePropertyName $ClaudeServerName -NotePropertyValue $geminiServer -Force
$geminiConfig | ConvertTo-Json -Depth 50 | Set-Content -Path $GeminiSettingsPath -Encoding UTF8

& claude mcp remove -s user $ClaudeServerName *> $null
$claudeAddArgs = @("mcp", "add", "-s", "user", $ClaudeServerName, "--", $serverSpec.command) + $serverSpec.args
& claude @claudeAddArgs | Out-Host

if (-not $SkipSkillInstall) {
    Assert-PathExists $SkillRepoRoot
    & npx skills add $SkillRepoRoot --skill ralph-hats --skill ralph-loop --skill ralph-orchestrator-setup -a codex claude-code gemini-cli -g -y | Out-Host
}

Write-Host "Installed Ralph Orchestrator CLI via $effectiveSource"
Write-Host "Codex MCP updated at $CodexConfigPath"
Write-Host "Claude MCP updated for $ClaudeServerName"
Write-Host "Gemini MCP updated at $GeminiSettingsPath"
