#!/usr/bin/env pwsh
<#
.SYNOPSIS
  cv/build.ps1 - one-command builds for the CV system. Canonical driver on Windows.

.DESCRIPTION
  Every target is a thin, honest wrapper around a Python entry point in this
  directory. This script adds NO rendering logic and NO facts of its own - it
  only sequences the drivers and propagates their exit codes.

  FAIL-CLOSED: the first non-zero exit stops the run and this script exits
  non-zero. A view that has no renderer prints SKIPPED from the driver itself
  and is NOT an error.

  The last line is always SUCCESS:<target> or FAILED:<target>.

.EXAMPLE
  ./build.ps1 help
  ./build.ps1 preflight
  ./build.ps1 all
  ./build.ps1 view research-profile
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)][string]$Target = 'help',
    [Parameter(Position = 1)][string]$Name   = '',
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = $PSScriptRoot
$Py   = Join-Path $Root '.venv/Scripts/python.exe'
$Out  = Join-Path $Root 'out'

# Target table. Keep the NAMES identical to the Makefile's .PHONY list;
# "./build.ps1 list" asserts that parity so the two drivers cannot silently drift.
$Targets = [ordered]@{
    'help'             = 'Print this table.'
    'list'             = 'List what the drivers actually expose (+ Makefile parity check).'
    'preflight'        = 'Check Python, venv, RenderCV, PyMuPDF are present and runnable.'
    'setup'            = 'Create .venv and install the render toolchain (one time).'
    'gate'             = 'Run the fail-closed zero-fabrication lint over profile.yaml.'
    'research-profile' = 'Deliverable #1: the one-page research profile (PDF + markdown fallback).'
    'views'            = 'All rendercv views via tools/build.py --all.'
    'view'             = 'One named view: ./build.ps1 view <name>.'
    'templates'        = 'ats-en + ro documents via templates/render_template.py --all.'
    'aux'              = 'Academic CV + cover letters + LinkedIn + platform packs + Europass.'
    'clean-copy'       = 'Same as aux with TODO markers omitted, into out/templates-clean.'
    'all'              = 'gate -> research-profile -> views -> templates -> aux -> clean-copy -> verify -> test.'
    'verify'           = 'Re-run the PDF no-regression contract over every PDF in out/.'
    'test'             = 'pytest (122 cases) + the three gate self-tests.'
    'clean'            = 'Delete out/ (generated documents only; never profile.yaml).'
}

function Write-Head([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }

function Invoke-Step {
    param([string]$Label, [string[]]$StepArgs)
    Write-Head $Label
    & $Py @StepArgs
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        throw "step '$Label' exited $code"
    }
}

function Assert-Venv {
    if (-not (Test-Path $Py)) {
        Write-Host "No venv at $Py" -ForegroundColor Red
        Write-Host 'Run:  ./build.ps1 setup      (or see REPRODUCE.md)' -ForegroundColor Yellow
        throw 'venv missing'
    }
}

function Show-Help {
    Write-Host ''
    Write-Host '  cv/build.ps1 - one-command builds' -ForegroundColor White
    Write-Host ''
    foreach ($k in $Targets.Keys) {
        Write-Host ('    {0,-18} {1}' -f $k, $Targets[$k])
    }
    Write-Host ''
    Write-Host '  Documents land in out/ . Nothing here invents a fact: every string' -ForegroundColor DarkGray
    Write-Host '  comes from profile.yaml and is gated by tools/zerofab.py.' -ForegroundColor DarkGray
    Write-Host ''
}

function Show-List {
    Assert-Venv
    Write-Head 'views exposed by tools/build.py'
    & $Py (Join-Path $Root 'tools/build.py') --list-views
    Write-Head 'templates exposed by templates/render_template.py'
    & $Py (Join-Path $Root 'templates/render_template.py') --list
    Write-Head 'auxiliary views exposed by templates/emit.py'
    & $Py (Join-Path $Root 'templates/emit.py') --list

    # Anti-rot: the Makefile must expose the same target names as this script.
    $mk = Join-Path $Root 'Makefile'
    if (Test-Path $mk) {
        Write-Head 'Makefile parity'
        $mkTargets = @(Select-String -Path $mk -Pattern '^\.PHONY:\s*(.+)$' |
            ForEach-Object { $_.Matches[0].Groups[1].Value -split '\s+' } |
            Where-Object { $_ })
        $mine   = @($Targets.Keys)
        $onlyPs = @($mine      | Where-Object { $mkTargets -notcontains $_ })
        $onlyMk = @($mkTargets | Where-Object { $mine      -notcontains $_ })
        if ($onlyPs.Count -eq 0 -and $onlyMk.Count -eq 0) {
            Write-Host '  OK    build.ps1 and Makefile expose the same targets' -ForegroundColor Green
        } else {
            if ($onlyPs.Count) { Write-Host "  DRIFT only in build.ps1: $($onlyPs -join ', ')" -ForegroundColor Yellow }
            if ($onlyMk.Count) { Write-Host "  DRIFT only in Makefile:  $($onlyMk -join ', ')" -ForegroundColor Yellow }
        }
    }
}

function Invoke-Preflight {
    $ok = $true
    Write-Head 'preflight'
    if (Test-Path $Py) {
        $v = & $Py -V 2>&1
        Write-Host "  OK    venv python  $v"
    } else {
        Write-Host "  MISS  venv python  ($Py)  -> ./build.ps1 setup" -ForegroundColor Yellow
        $ok = $false
    }
    if ($ok) {
        $probes = @(
            @{ n = 'rendercv'; c = 'import importlib.metadata as m; print(m.version("rendercv"))' },
            @{ n = 'pymupdf' ; c = 'import importlib.metadata as m; print(m.version("pymupdf"))' },
            @{ n = 'pyyaml'  ; c = 'import yaml; print(yaml.__version__)' },
            @{ n = 'typst'   ; c = 'import importlib.metadata as m; print(m.version("typst"))' }
        )
        foreach ($probe in $probes) {
            $val = & $Py -c $probe.c 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host ('  OK    {0,-10} {1}' -f $probe.n, $val)
            } else {
                Write-Host ('  MISS  {0}' -f $probe.n) -ForegroundColor Yellow
                $ok = $false
            }
        }
    }
    $prof = Join-Path $Root 'profile.yaml'
    if (Test-Path $prof) {
        Write-Host "  OK    profile.yaml  $((Get-Item $prof).Length) bytes"
    } else {
        Write-Host '  MISS  profile.yaml' -ForegroundColor Red
        $ok = $false
    }
    if (-not $ok) { throw 'preflight failed - see REPRODUCE.md' }
}

function Invoke-Setup {
    Write-Head 'setup: creating .venv and installing the render toolchain'
    $sys = 'C:/Python314/python.exe'
    if (-not (Test-Path $sys)) { $sys = 'python' }
    & $sys -m venv (Join-Path $Root '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
    & $Py -m pip install --upgrade pip
    & $Py -m pip install 'rendercv[full]' pymupdf ruamel.yaml pyyaml jinja2 pytest ruff
    if ($LASTEXITCODE -ne 0) { throw 'dependency install failed' }
    Invoke-Preflight
}

function Invoke-VerifyAll {
    Assert-Venv
    # Only DELIVERABLES are swept. tools/verify.py --selftest writes deliberately
    # broken fixtures (US-Letter, two-column, ligature-damaged) into out/_selftest/
    # to prove each check fires; verifying those would fail by design. Any
    # underscore-prefixed directory under out/ is fixtures, not documents.
    $pdfs = @(Get-ChildItem -Path $Out -Filter *.pdf -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '[\\/]_[^\\/]*[\\/]' })
    if ($pdfs.Count -eq 0) {
        Write-Host '  (no deliverable PDFs in out/ yet - nothing to verify)'
        return
    }
    foreach ($p in $pdfs) {
        Write-Head "verify $($p.Name)"
        & $Py (Join-Path $Root 'tools/verify.py') --pdf $p.FullName
        if ($LASTEXITCODE -ne 0) { throw "verify failed on $($p.Name)" }
    }
}

function Invoke-Tests {
    Assert-Venv
    Invoke-Step 'pytest' @('-m', 'pytest',
        (Join-Path $Root 'tools/test_zerofab.py'),
        (Join-Path $Root 'tools/test_build.py'),
        (Join-Path $Root 'templates/test_templates.py'), '-q')
    Invoke-Step 'verify-selftest'   @((Join-Path $Root 'tools/verify.py'), '--selftest')
    Invoke-Step 'docgate-selftest'  @((Join-Path $Root 'templates/docgate.py'), '--selftest')
    Invoke-Step 'killlist-selftest' @((Join-Path $Root 'templates/killlist.py'), '--self-test')
}

try {
    switch ($Target) {
        'help'      { Show-Help }
        'list'      { Show-List }
        'preflight' { Invoke-Preflight }
        'setup'     { Invoke-Setup }
        'clean' {
            Write-Head 'clean'
            if (Test-Path $Out) {
                Remove-Item -Recurse -Force $Out
                Write-Host '  removed out/'
            } else {
                Write-Host '  out/ already absent'
            }
        }
        'gate' {
            Assert-Venv
            Invoke-Step 'gate' @((Join-Path $Root 'tools/zerofab.py'), (Join-Path $Root 'profile.yaml'))
        }
        'research-profile' {
            Assert-Venv
            Invoke-Step 'research-profile' @((Join-Path $Root 'templates/research-profile/render.py'))
        }
        'views' {
            Assert-Venv
            Invoke-Step 'views' @((Join-Path $Root 'tools/build.py'), '--all')
        }
        'view' {
            Assert-Venv
            if (-not $Name) { throw 'usage: ./build.ps1 view <name>   (see ./build.ps1 list)' }
            Invoke-Step "view:$Name" @((Join-Path $Root 'tools/build.py'), '--view', $Name)
        }
        'templates' {
            Assert-Venv
            Invoke-Step 'templates' @((Join-Path $Root 'templates/render_template.py'), '--all')
        }
        'aux' {
            Assert-Venv
            Invoke-Step 'aux' @((Join-Path $Root 'templates/emit.py'), '--all')
        }
        'clean-copy' {
            Assert-Venv
            Invoke-Step 'clean-copy' @((Join-Path $Root 'templates/emit.py'), '--all',
                '--todo', 'omit', '--out', (Join-Path $Out 'templates-clean'))
        }
        'all' {
            Assert-Venv
            Invoke-Preflight
            Invoke-Step 'gate'             @((Join-Path $Root 'tools/zerofab.py'), (Join-Path $Root 'profile.yaml'))
            Invoke-Step 'research-profile' @((Join-Path $Root 'templates/research-profile/render.py'))
            Invoke-Step 'views'            @((Join-Path $Root 'tools/build.py'), '--all')
            Invoke-Step 'templates'        @((Join-Path $Root 'templates/render_template.py'), '--all')
            Invoke-Step 'aux'              @((Join-Path $Root 'templates/emit.py'), '--all')
            Invoke-Step 'clean-copy'       @((Join-Path $Root 'templates/emit.py'), '--all',
                '--todo', 'omit', '--out', (Join-Path $Out 'templates-clean'))
            Invoke-VerifyAll
            if (-not $SkipTests) { Invoke-Tests }
        }
        'verify' { Invoke-VerifyAll }
        'test'   { Invoke-Tests }
        default {
            Write-Host "unknown target '$Target'" -ForegroundColor Red
            Show-Help
            throw "unknown target '$Target'"
        }
    }
} catch {
    Write-Host ''
    Write-Host "FAILED:$Target  $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host "SUCCESS:$Target" -ForegroundColor Green
exit 0
