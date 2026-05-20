# Validates the live skills surface only. Tool validation stays tool-specific
# until runnable MCP or web projects exist under tools/.
param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$ValidatorPath
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

if (-not $ValidatorPath) {
    $codexHome = if ($env:CODEX_HOME) {
        $env:CODEX_HOME
    } else {
        Join-Path ([Environment]::GetFolderPath("UserProfile")) ".codex"
    }

    $validatorCandidates = @(
        (Join-Path $codexHome ".agents/skills/.system/skill-creator/scripts/quick_validate.py"),
        (Join-Path $codexHome "skills/.system/skill-creator/scripts/quick_validate.py")
    )
    $ValidatorPath = $validatorCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not (Test-Path $ValidatorPath)) {
    throw "Validator not found at $ValidatorPath"
}

function Get-PythonCandidateSpec {
    $candidates = @()

    if ($env:CODEX_PYTHON_WITH_YAML) {
        $candidates += ,@($env:CODEX_PYTHON_WITH_YAML)
    }

    $localAppData = [Environment]::GetFolderPath("LocalApplicationData")
    foreach ($root in @((Join-Path $localAppData "Programs\Python"), (Join-Path $localAppData "Python"))) {
        if (-not (Test-Path $root)) { continue }
        Get-ChildItem -Path $root -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object {
                $pythonPath = Join-Path $_.FullName "python.exe"
                if (Test-Path $pythonPath) {
                    $candidates += ,@($pythonPath)
                }
            }
    }

    foreach ($name in @("python", "py", "python3")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            if ($command.Name -eq "py.exe") {
                $candidates += ,@($command.Source, "-3")
            } else {
                $candidates += ,@($command.Source)
            }
        }
    }

    $seen = New-Object 'System.Collections.Generic.HashSet[string]'
    foreach ($candidate in $candidates) {
        $key = ($candidate -join "|")
        if ($seen.Add($key)) {
            ,$candidate
        }
    }
}

function Test-PythonHasYaml {
    param([string[]]$CommandSpec)

    $command = $CommandSpec[0]
    $rest = if ($CommandSpec.Length -gt 1) { $CommandSpec[1..($CommandSpec.Length - 1)] } else { @() }
    & $command @rest -c "import yaml" *> $null
    return ($LASTEXITCODE -eq 0)
}

$pythonSpec = Get-PythonCandidateSpec | Where-Object { Test-PythonHasYaml $_ } | Select-Object -First 1
if (-not $pythonSpec) {
    throw "No Python interpreter with PyYAML found. Install PyYAML or set CODEX_PYTHON_WITH_YAML."
}
Write-Host ("Using Python interpreter: " + ($pythonSpec -join " "))

$skillsRoot = if (Test-Path (Join-Path $Root ".agents\skills")) {
    Join-Path $Root ".agents\skills"
} else {
    Join-Path $Root "skills"
}

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
    $command = $pythonSpec[0]
    $rest = if ($pythonSpec.Length -gt 1) { $pythonSpec[1..($pythonSpec.Length - 1)] } else { @() }
    & $command @rest $ValidatorPath $skill.FullName
    if ($LASTEXITCODE -ne 0) {
        $failures += $skill.Name
    }
}

if ($failures.Count -gt 0) {
    throw "Validation failed for: $($failures -join ', ')"
}

Write-Host "Validated $($skills.Count) skill(s) successfully."
