param(
    [string]$InstallRoot = "C:\Users\Prekzursil\.local\opt\hexstrike-ai",
    [string]$Ref = "83337796dcfb8cfbf733bd24d0b2c7e4f0732790"
)

$ErrorActionPreference = 'Stop'

$repoUrl = 'https://github.com/0x4m4/hexstrike-ai.git'
$venvPython = Join-Path $InstallRoot '.venv\Scripts\python.exe'
$launcherSource = Join-Path $PSScriptRoot 'hexstrike_mcp_launcher.py'
$launcherTarget = Join-Path $InstallRoot 'hexstrike_mcp_launcher.py'

if (Test-Path $InstallRoot) {
    git -C $InstallRoot fetch origin --depth=1
    git -C $InstallRoot reset --hard $Ref
} else {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $InstallRoot) | Out-Null
    git clone $repoUrl $InstallRoot
    git -C $InstallRoot checkout $Ref
}

py -3.11 -m venv (Join-Path $InstallRoot '.venv')
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $InstallRoot 'requirements.txt')
Copy-Item -Force $launcherSource $launcherTarget

Write-Host "Installed HexStrike AI at $InstallRoot"
Write-Host "Launcher copied to $launcherTarget"
