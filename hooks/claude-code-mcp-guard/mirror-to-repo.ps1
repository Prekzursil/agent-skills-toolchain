# mirror-to-repo.ps1 -- copy the claude-code-mcp-guard hook (live tree) into the
# agent-skills-toolchain repo canonical so live == repo (zero drift). Read-only wrt git.

$ErrorActionPreference = 'Stop'

$src = 'C:\Users\Prekzursil\.claude\hooks\claude-code-mcp-guard'
$dst = 'C:\Users\Prekzursil\source\agent-skills-toolchain\hooks\claude-code-mcp-guard'

if (-not (Test-Path $dst)) {
    New-Item -ItemType Directory -Path $dst | Out-Null
}

foreach ($f in @('guard.py', 'selftest.py', 'validate-and-pipetest.ps1', 'verify-entry.ps1', 'SELFTEST-EVIDENCE.md')) {
    Copy-Item -LiteralPath (Join-Path $src $f) -Destination $dst -Force
}

'--- repo dir contents:'
Get-ChildItem -LiteralPath $dst | ForEach-Object { '{0} {1}' -f $_.Name, $_.Length }

'hash-match-guard: ' + ((Get-FileHash -LiteralPath (Join-Path $src 'guard.py')).Hash -eq (Get-FileHash -LiteralPath (Join-Path $dst 'guard.py')).Hash)
'hash-match-evidence: ' + ((Get-FileHash -LiteralPath (Join-Path $src 'SELFTEST-EVIDENCE.md')).Hash -eq (Get-FileHash -LiteralPath (Join-Path $dst 'SELFTEST-EVIDENCE.md')).Hash)

'--- git status (scoped, read-only):'
git -C 'C:\Users\Prekzursil\source\agent-skills-toolchain' status --porcelain -- hooks/claude-code-mcp-guard
