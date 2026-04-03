param(
    [string]$InstallRoot = "C:\Users\Prekzursil\.local\opt\cheatengine-mcp-bridge",
    [string]$CheatEngineInstallDir = "C:\Program Files\Cheat Engine",
    [string]$CodexConfigPath = "C:\Users\Prekzursil\.codex\config.toml",
    [string]$Ref = "cc7965094781209768c71a0ec3ab5dfcd20e24a2"
)

$ErrorActionPreference = 'Stop'

# Stop rules:
# - Close Cheat Engine before reinstalling or updating the autorun wrapper.
# - This script installs the bridge and config only. It does not validate memory writes.

$repoUrl = 'https://github.com/miscusi-peek/cheatengine-mcp-bridge.git'
$venvPython = Join-Path $InstallRoot '.venv\Scripts\python.exe'
$bridgePython = Join-Path $InstallRoot 'MCP_Server\mcp_cheatengine.py'
$bridgeLua = Join-Path $InstallRoot 'MCP_Server\ce_mcp_bridge.lua'
$autorunWrapper = Join-Path $CheatEngineInstallDir 'autorun\zz_ce_mcp_bridge.lua'
$logPath = Join-Path $InstallRoot 'autorun-bootstrap.log'

if (Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match 'cheatengine' }) {
    throw 'Close all Cheat Engine processes before running this install script.'
}

if (Test-Path $InstallRoot) {
    git -C $InstallRoot fetch --depth=1 origin
    git -C $InstallRoot reset --hard $Ref
} else {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $InstallRoot) | Out-Null
    git clone $repoUrl $InstallRoot
    git -C $InstallRoot checkout $Ref
}

python -m venv (Join-Path $InstallRoot '.venv')
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $InstallRoot 'MCP_Server\requirements.txt')

$wrapper = @"
local logPath = '$($logPath -replace '\\','/')'
local bridgePath = '$($bridgeLua -replace '\\','/')'
local originalPrint = print
local function writeLog(msg)
  local ok, f = pcall(io.open, logPath, 'a')
  if ok and f then
    f:write(os.date('%Y-%m-%d %H:%M:%S') .. ' ' .. tostring(msg) .. '\n')
    f:close()
  end
end
function print(...)
  local parts = {}
  for i = 1, select('#', ...) do
    parts[#parts + 1] = tostring(select(i, ...))
  end
  writeLog(table.concat(parts, ' '))
  if originalPrint then originalPrint(...) end
end
onLuaError = function(err)
  writeLog('lua error: ' .. tostring(err))
  return err
end
writeLog('autorun wrapper entered')
local ok, err = pcall(function()
  dofile(bridgePath)
end)
if ok then
  writeLog('bridge loaded successfully')
else
  writeLog('bridge load failed: ' .. tostring(err))
end
"@
Set-Content -Path $autorunWrapper -Value $wrapper -Encoding UTF8

$configText = Get-Content -Raw $CodexConfigPath
if ($configText -notmatch '\[mcp_servers\.cheatengine\]') {
    $configText += @"

[mcp_servers.cheatengine]
command = "$($venvPython -replace '\\','/')"
args = ["$($bridgePython -replace '\\','/')"]
enabled = true
"@
    Set-Content -Path $CodexConfigPath -Value $configText -Encoding UTF8
}

Write-Host "Installed cheatengine-mcp-bridge at $InstallRoot"
Write-Host "Autorun wrapper: $autorunWrapper"
Write-Host "Codex config: $CodexConfigPath"
