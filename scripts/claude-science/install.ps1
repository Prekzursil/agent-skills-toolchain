# Install the Claude Science cs-* launchers onto PATH (Windows + WSL). No admin needed.
# Windows: copies cs-start/cs-recover .ps1+.cmd into ~\.local\bin (must be on your user PATH).
# WSL:     copies the extension-less bash scripts into ~/.local/bin (already on WSL PATH).
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$winDir = Join-Path $env:USERPROFILE '.local\bin'
New-Item -ItemType Directory -Force -Path $winDir | Out-Null
foreach ($f in 'cs-start.ps1','cs-start.cmd','cs-recover.ps1','cs-recover.cmd','start-claude-science.ps1') {
  $src = Join-Path $here $f
  if (Test-Path $src) { Copy-Item $src (Join-Path $winDir $f) -Force; Write-Host "[win] $f" }
}

# WSL: strip CR and install as extension-less commands
foreach ($f in 'cs-start.sh','cs-recover.sh','cs-install.sh','cs-serve-prep.sh','cs-finish.sh') {
  $src = Join-Path $here $f
  if (Test-Path $src) {
    $name = [IO.Path]::GetFileNameWithoutExtension($f)
    $wslSrc = ($src -replace '\\','/') -replace '^C:','/mnt/c'
    wsl.exe -d Ubuntu -- bash -lc "mkdir -p ~/.local/bin && tr -d '\r' < '$wslSrc' > ~/.local/bin/$name && chmod +x ~/.local/bin/$name && echo '[wsl] $name'"
  }
}
Write-Host "Done. Ensure $winDir is on your Windows user PATH; ~/.local/bin is on WSL PATH by default."
