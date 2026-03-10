param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$ValidatorPath
)

$ErrorActionPreference = "Stop"

if (-not $ValidatorPath) {
    $codexHome = if ($env:CODEX_HOME) {
        $env:CODEX_HOME
    } else {
        Join-Path ([Environment]::GetFolderPath("UserProfile")) ".codex"
    }

    $ValidatorPath = Join-Path $codexHome "skills/.system/skill-creator/scripts/quick_validate.py"
}

if (-not (Test-Path $ValidatorPath)) {
    throw "Validator not found at $ValidatorPath"
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command py -ErrorAction SilentlyContinue
}

if (-not $python) {
    throw "Python launcher not found. Install Python or pass a custom validation command."
}

$skillsRoot = Join-Path $Root "skills"
if (-not (Test-Path $skillsRoot)) {
    throw "Skills root not found at $skillsRoot"
}

$skills = Get-ChildItem $skillsRoot -Directory | Where-Object {
    Test-Path (Join-Path $_.FullName "SKILL.md")
}

if (-not $skills) {
    throw "No skills found under $skillsRoot"
}

$failures = @()

foreach ($skill in $skills) {
    Write-Host "Validating $($skill.Name)..."

    if ($python.Name -eq "py.exe") {
        & $python.Source -3 $ValidatorPath $skill.FullName
    } else {
        & $python.Source $ValidatorPath $skill.FullName
    }

    if ($LASTEXITCODE -ne 0) {
        $failures += $skill.Name
    }
}

if ($failures.Count -gt 0) {
    throw "Validation failed for: $($failures -join ', ')"
}

Write-Host "Validated $($skills.Count) skill(s) successfully."
