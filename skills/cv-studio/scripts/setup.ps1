#Requires -Version 7.0
<#
.SYNOPSIS
  One-time cv-studio engine setup (Windows). Creates an ISOLATED venv and installs
  RenderCV[full] (bundled Typst) + PyMuPDF into it, so global Python is never polluted.
.NOTES
  Why isolated: rendercv[full] pins typer>=0.25, which conflicts with docling (<0.25).
  Installing into a dedicated venv keeps the owner's global env intact. Idempotent.
#>
[CmdletBinding()]
param(
  [string]$VenvPath = (Join-Path $HOME ".local\share\cv-studio\venv")
)
$ErrorActionPreference = "Stop"

Write-Host "cv-studio setup -> $VenvPath"
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { Write-Error "FAILED: python not found on PATH."; exit 1 }

if (-not (Test-Path $VenvPath)) {
  New-Item -ItemType Directory -Force (Split-Path $VenvPath) | Out-Null
  & $py -m venv $VenvPath
}
$venvPy = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path $venvPy)) { Write-Error "FAILED: venv python missing at $venvPy"; exit 1 }

& $venvPy -m pip install --upgrade --quiet pip
& $venvPy -m pip install --upgrade --quiet "rendercv[full]" pymupdf
if ($LASTEXITCODE -ne 0) { Write-Error "FAILED: pip install rendercv[full] pymupdf"; exit 1 }

$rcv = Join-Path $VenvPath "Scripts\rendercv.exe"
$ver = & $rcv --version 2>&1
Write-Host "  rendercv: $ver"

# Smoke: render the bundled sample and self-check it.
$skill = Split-Path $PSScriptRoot -Parent
$sample = Join-Path $skill "assets\sample-profile.yaml"
$out = Join-Path $env:TEMP "cv-studio-smoke"
if (Test-Path $sample) {
  & $venvPy (Join-Path $PSScriptRoot "cvstudio.py") build $sample --out $out
  if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS: cv-studio ready. Run scripts with:`n  $venvPy scripts\cvstudio.py build profile.yaml"
  } else { Write-Error "FAILED: smoke build did not pass."; exit 1 }
} else {
  Write-Host "SUCCESS: engine installed (sample not found; skipped smoke)."
}
