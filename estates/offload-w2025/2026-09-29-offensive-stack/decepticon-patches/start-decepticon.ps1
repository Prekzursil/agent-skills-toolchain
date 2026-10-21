# start-decepticon.ps1 - full local Decepticon stack, loopback-only.
# Starts: 3 MCP tool servers (recon :3001, initial-access :3002, terminal :3003),
# then optionally the Streamlit UI (127.0.0.1:8501). All tools run dual-mode
# (kali container when Docker is up, local Git Bash otherwise).
param(
    [switch]$NoUi
)
$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot
$Py   = Join-Path $Root ".venv\Scripts\python.exe"
$Log  = "D:\tmp"
$env:DECEPTICON_FORCE = ""          # auto: kali container if Docker is up, else local
# estate keys for any search usage inside agents
$env:TAVILY_API_KEY  = [Environment]::GetEnvironmentVariable("TAVILY_API_KEY",  "User")
$env:TAVILY_API_KEY2 = [Environment]::GetEnvironmentVariable("TAVILY_API_KEY_2", "User")
$env:EXA_API_KEY     = [Environment]::GetEnvironmentVariable("EXA_API_KEY",     "User")
$env:FIRECRAWL_API_KEY = [Environment]::GetEnvironmentVariable("FIRECRAWL_API_KEY", "User")

$mcpDir = Join-Path $Root "src\tools\mcp"
foreach ($srv in @("Reconnaissance.py", "Initial_Access.py", "terminal.py")) {
    Start-Process -FilePath $Py -ArgumentList @((Join-Path $mcpDir $srv)) `
        -WorkingDirectory $mcpDir -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $Log ("dc-" + $srv + ".out.log")) `
        -RedirectStandardError  (Join-Path $Log ("dc-" + $srv + ".err.log"))
}
Write-Host "MCP fronts started: reconnaissance :3001, initial-access :3002, terminal :3003"

if (-not $NoUi) {
    Start-Process -FilePath $Py -ArgumentList @("-m", "streamlit", "run", "frontend\streamlit_app.py", `
        "--server.address", "127.0.0.1", "--server.port", "8501", "--browser.gatherUsageStats", "false") `
        -WorkingDirectory $Root -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $Log "dc-streamlit.out.log") `
        -RedirectStandardError  (Join-Path $Log "dc-streamlit.err.log")
    Write-Host "Streamlit UI: http://127.0.0.1:8501 (loopback only)"
}
Write-Host "Note: CLI mode - .\.venv\Scripts\python.exe frontend\cli\cli.py"
