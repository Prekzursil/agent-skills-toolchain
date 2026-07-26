#requires -Version 7
<#
.SYNOPSIS
  Reviewed, idempotent Windows deployment of the hardened HackTricks MCP server.

.DESCRIPTION
  Builds and tests the standalone project, stages a production copy into a unique
  temporary directory, explicitly provisions the pinned corpus with corpus hooks
  disabled, runs a harmless read-only MCP smoke test, backs up any existing exact
  install root, atomically replaces ONLY that validated root, and writes a
  non-sensitive receipt. It never executes a dependency lifecycle script, never
  auto-fetches the corpus on startup/lookup/CI, and never recursively deletes a
  broad or unresolved path.

  Human-gated: this mutates live estate state and is not run by CI.
#>
[CmdletBinding()]
param(
  [string]$InstallRoot = (Join-Path $env:USERPROFILE '.local\opt\hacktricks-mcp-server'),
  [string]$CorpusRepo = 'https://github.com/HackTricks-wiki/hacktricks.git',
  [string]$CorpusCommit = '346301958c8bf94120ba0aaaaf9cd963997bdac3',
  [string]$OfficialOrigin = 'https://github.com/hacktricks-wiki/hacktricks'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Require-Command {
  param([string]$Name)
  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if ($null -eq $cmd) { throw "required command not found on PATH: $Name" }
  return $cmd
}

function Invoke-Checked {
  param([string]$File, [string[]]$Arguments, [string]$WorkDir)
  Push-Location $WorkDir
  try {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$File $($Arguments -join ' ') exited $LASTEXITCODE" }
  } finally {
    Pop-Location
  }
}

function Normalize-Origin {
  param([string]$Url)
  $u = $Url.Trim()
  if ($u.EndsWith('.git')) { $u = $u.Substring(0, $u.Length - 4) }
  if ($u.EndsWith('/')) { $u = $u.Substring(0, $u.Length - 1) }
  return $u.ToLowerInvariant()
}

$project = Split-Path -Parent $PSScriptRoot
Write-Host "[hacktricks-mcp] project: $project"

# 1. prerequisites
Require-Command 'npm' | Out-Null
Require-Command 'git' | Out-Null
Require-Command 'rg' | Out-Null
$node = Require-Command 'node'
$nodeVersion = (& $node.Source '--version').TrimStart('v')
$nodeMajor = [int]($nodeVersion.Split('.')[0])
if ($nodeMajor -lt 22) { throw "Node 22+ required; found $nodeVersion" }

if (-not (Test-Path -LiteralPath (Join-Path $project 'package.json'))) { throw 'package.json missing' }
if (-not (Test-Path -LiteralPath (Join-Path $project 'package-lock.json'))) { throw 'package-lock.json missing' }

# 2. install (scripts ignored), build + full test/coverage gate
Invoke-Checked -File 'npm' -Arguments @('ci', '--ignore-scripts', '--no-audit', '--no-fund') -WorkDir $project
Invoke-Checked -File 'npm' -Arguments @('test') -WorkDir $project

# 3. stage a production copy
$stage = Join-Path $env:TEMP ('hacktricks-mcp-stage-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
  foreach ($f in @('package.json', 'package-lock.json')) {
    Copy-Item -LiteralPath (Join-Path $project $f) -Destination (Join-Path $stage $f)
  }
  Copy-Item -LiteralPath (Join-Path $project 'dist') -Destination (Join-Path $stage 'dist') -Recurse
  Invoke-Checked -File 'npm' -Arguments @('ci', '--omit=dev', '--ignore-scripts', '--no-audit', '--no-fund') -WorkDir $stage

  # 4. provision the pinned corpus with corpus hooks disabled
  $book = Join-Path $stage 'hacktricks'
  $emptyHooks = Join-Path $stage 'empty-hooks'
  New-Item -ItemType Directory -Path $emptyHooks | Out-Null
  $env:GIT_TERMINAL_PROMPT = '0'
  & git '-c' "core.hooksPath=$emptyHooks" clone --no-checkout --no-recurse-submodules $CorpusRepo $book
  if ($LASTEXITCODE -ne 0) { throw 'corpus clone failed' }
  & git '-C' $book config core.hooksPath $emptyHooks
  & git '-C' $book '-c' "core.hooksPath=$emptyHooks" fetch --no-recurse-submodules origin $CorpusCommit
  if ($LASTEXITCODE -ne 0) { throw 'corpus fetch of pinned commit failed' }
  & git '-C' $book '-c' "core.hooksPath=$emptyHooks" checkout --detach $CorpusCommit
  if ($LASTEXITCODE -ne 0) { throw 'corpus detach to pinned commit failed' }

  # 5. verify corpus + built entrypoint
  $origin = (& git '-C' $book remote get-url origin).Trim()
  if ((Normalize-Origin $origin) -ne (Normalize-Origin $OfficialOrigin)) { throw "corpus origin mismatch: $origin" }
  $head = (& git '-C' $book rev-parse HEAD).Trim()
  if ($head -ne $CorpusCommit) { throw "corpus HEAD mismatch: $head" }
  $porcelain = (& git '-C' $book status --porcelain --untracked-files=no)
  if (-not [string]::IsNullOrWhiteSpace(($porcelain -join ''))) { throw 'corpus working tree is dirty' }
  if (-not (Test-Path -LiteralPath (Join-Path $book 'src/SUMMARY.md'))) { throw 'corpus src/SUMMARY.md missing' }
  $entry = Join-Path $stage 'dist/index.js'
  if (-not (Test-Path -LiteralPath $entry)) { throw 'built dist/index.js missing' }
  $blob = (& git '-C' $book rev-parse 'HEAD:src/SUMMARY.md').Trim()

  # 6. harmless read-only MCP smoke test (list tools; never calls a tool)
  $env:HACKTRICKS_CORPUS = $book
  $smokeOut = & $node.Source (Join-Path $project 'scripts/smoke.mjs') $entry
  if ($LASTEXITCODE -ne 0) { throw "MCP smoke test failed: $smokeOut" }

  # 7. backup existing exact install root, then atomically replace only it
  $parent = Split-Path -Parent $InstallRoot
  if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
  if (Test-Path -LiteralPath $InstallRoot) {
    $backup = "$InstallRoot.backup-" + (Get-Date -Format 'yyyyMMdd-HHmmss')
    Move-Item -LiteralPath $InstallRoot -Destination $backup
    Write-Host "[hacktricks-mcp] backed up existing install to $backup"
  }
  Remove-Item -LiteralPath $emptyHooks -Recurse -Force
  Move-Item -LiteralPath $stage -Destination $InstallRoot

  # 8. non-sensitive receipt
  $wrapperCommit = (& git '-C' $project rev-parse HEAD).Trim()
  $lockHash = (Get-FileHash -LiteralPath (Join-Path $InstallRoot 'package-lock.json') -Algorithm SHA256).Hash
  $receipt = [ordered]@{
    install_path         = $InstallRoot
    wrapper_source_commit = $wrapperCommit
    package_lock_sha256  = $lockHash
    corpus_repository    = (Normalize-Origin $origin)
    corpus_revision      = $head
    corpus_summary_blob  = $blob
    node_version         = $nodeVersion
    npm_version          = (& npm '--version').Trim()
    git_version          = (& git '--version').Trim()
    rg_version           = ((& rg '--version') | Select-Object -First 1)
    smoke_result         = ($smokeOut | Out-String).Trim()
    tests                = 'passed (npm test: build + node --test 100% line/branch/function)'
    generated_at         = (Get-Date -Format 'o')
  }
  $receiptPath = Join-Path $InstallRoot 'install-receipt.json'
  ($receipt | ConvertTo-Json -Depth 4) | Set-Content -LiteralPath $receiptPath -Encoding UTF8
  Write-Host "[hacktricks-mcp] installed to $InstallRoot"
  Write-Host "[hacktricks-mcp] receipt: $receiptPath"
} catch {
  if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue }
  throw
}
