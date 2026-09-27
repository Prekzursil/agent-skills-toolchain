<#
.SYNOPSIS
  Copy the authored-and-irreplaceable subset of ~/.claude into the version-controlled
  ~/.agents repo, so the harness config stops relying on dated .bak files as version control.

.DESCRIPTION
  ~/.claude is 14.218 GB and is NOT a git repo. Only ~461 files / 9.18 MB of it is authored
  and irreplaceable. This script copies exactly that set - named by
  harness-baseline/baseline-manifest.txt - into harness-baseline/dot-claude/ inside ~/.agents,
  which IS version-controlled.

  THREE GATES, each of which can fail the run:

    CRED   Refuse to copy anything matching a credential/secret pattern. Enforced twice:
           once when selecting sources, and once as a post-copy sweep of the destination.
           A single hit fails the run non-zero. Nothing is ever printed from these files.

    IGNORE Refuse to report success if git would ignore what was written. This is the gate
           that matters most: ~/.agents/.gitignore ignores backups/, deploy-backups/ and
           *.bak-*, so a backup written to the obvious place is INVISIBLE to git - a backup
           that looks done and is not. After copying, every destination path is run through
           `git check-ignore`; any ignored path fails the run.

    DEST   Refuse to write outside harness-baseline/dot-claude/ under the repo root.

  It does NOT commit (the caller commits) and it does NOT delete anything in ~/.claude.

.PARAMETER DryRun
  Select and report, copy nothing.

.PARAMETER SelfTest
  Both-states proof: build a fixture repo with a .gitignore that mimics the real one, then
  assert the CRED gate blocks a credential file, the IGNORE gate catches a git-ignored
  destination, the DEST gate rejects an out-of-tree destination, and that a clean set copies
  and verifies. Exits non-zero on any misclassification.

.PARAMETER ClaudeRoot / RepoRoot / Manifest
  Overridable for the self-test.
#>
[CmdletBinding()]
param(
  [switch]$DryRun,
  [switch]$SelfTest,
  [string]$ClaudeRoot = "$env:USERPROFILE\.claude",
  [string]$RepoRoot   = "$env:USERPROFILE\.agents",
  [string]$Manifest   = '',
  [string]$DestRel    = 'harness-baseline/dot-claude'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Patterns that must NEVER be copied, independent of the manifest. Defence in depth: the
# manifest also denies these, and ~/.agents/.gitignore ignores them. All three must agree.
#
# These match a credential STORE, and are deliberately anchored to the FILE NAME, never a
# substring of the path. A bare 'credential' substring test was tried first and was WRONG:
# it silently dropped hooks/deny-credential-reads/{deny.py,test_deny.py,
# test_denylist_coverage.py,test_guard_scope.py} - the source of the hook that GUARDS
# credentials - because its directory name contains the word. A backup that quietly omits
# the credential guard is worse than no gate, so the heuristic is now name-anchored and
# source-code extensions are exempt from it.
$CRED_RX = @(
  '(^|/)\.?credentials?(\.json)?$',   # .credentials.json, credentials.json, credentials
  '(^|/)[^/]*-credentials?\.json$',   # foo-credentials.json
  '\.pem$', '\.key$', '\.pfx$', '\.p12$', '\.jks$', '\.keystore$',
  '(^|/)\.?[^/]*\.token$',
  '(^|/)[^/]*(auth|token|secret)[^/]*\.json$',
  '(^|/)\.env$', '(^|/)\.env\.', '(^|/)\.netrc$', '(^|/)\.htpasswd$',
  '(^|/)id_(rsa|dsa|ecdsa|ed25519)$'
)

# Extensions that are source code or documentation. A credential is not shipped as source,
# so the name-anchored heuristic above does not apply to these - except for the exact-name
# denies (.env, .netrc, id_rsa) which are checked regardless.
$CRED_EXEMPT_EXT = @('.py','.ts','.js','.mjs','.cjs','.sh','.bash','.ps1','.psm1','.md','.txt','.rst','.toml','.yaml','.yml','.ini','.cfg','.html','.css')
$CRED_ALWAYS_RX  = @('(^|/)\.env$','(^|/)\.env\.','(^|/)\.netrc$','(^|/)\.htpasswd$','(^|/)id_(rsa|dsa|ecdsa|ed25519)$','\.pem$','\.key$','\.pfx$','\.p12$')

function Test-CredentialPath {
  param([Parameter(Mandatory)][string]$RelPath)
  $p = $RelPath.Replace('\','/').ToLower()
  # unconditional denies first - these apply even to source-shaped names
  foreach ($rx in $CRED_ALWAYS_RX) { if ($p -match $rx) { return $true } }
  $ext = [System.IO.Path]::GetExtension($p)
  if ($CRED_EXEMPT_EXT -contains $ext) { return $false }
  foreach ($rx in $CRED_RX) { if ($p -match $rx) { return $true } }
  return $false
}

function Convert-GlobToRegex {
  param([Parameter(Mandatory)][string]$Glob)
  $g = $Glob.Replace('\','/')
  $sb = New-Object System.Text.StringBuilder
  [void]$sb.Append('^')
  $i = 0
  while ($i -lt $g.Length) {
    $c = $g[$i]
    if ($c -eq '*') {
      if ($i + 1 -lt $g.Length -and $g[$i+1] -eq '*') {
        # '**/' matches zero or more path segments; bare '**' matches anything
        if ($i + 2 -lt $g.Length -and $g[$i+2] -eq '/') { [void]$sb.Append('(?:.*/)?'); $i += 3; continue }
        [void]$sb.Append('.*'); $i += 2; continue
      }
      [void]$sb.Append('[^/]*'); $i++; continue
    }
    if ($c -eq '?') { [void]$sb.Append('[^/]'); $i++; continue }
    [void]$sb.Append([regex]::Escape([string]$c)); $i++
  }
  [void]$sb.Append('$')
  return $sb.ToString()
}

function Read-Manifest {
  param([Parameter(Mandatory)][string]$Path)
  $inc = New-Object System.Collections.Generic.List[string]
  $den = New-Object System.Collections.Generic.List[string]
  foreach ($raw in (Get-Content -LiteralPath $Path)) {
    $l = $raw.Trim()
    if (-not $l -or $l.StartsWith('#')) { continue }
    if ($l.StartsWith('!')) { $den.Add((Convert-GlobToRegex $l.Substring(1))) }
    else                    { $inc.Add((Convert-GlobToRegex $l)) }
  }
  return [pscustomobject]@{ Include = $inc; Deny = $den }
}

function Select-BaselineFiles {
  param(
    [Parameter(Mandatory)][string]$Root,
    [Parameter(Mandatory)]$Rules
  )
  $opt = New-Object System.IO.EnumerationOptions
  $opt.RecurseSubdirectories = $true
  $opt.IgnoreInaccessible = $true
  $opt.AttributesToSkip = [System.IO.FileAttributes]::ReparsePoint

  $sel = New-Object System.Collections.Generic.List[object]
  $denied = 0; $credBlocked = 0
  $di = New-Object System.IO.DirectoryInfo $Root
  foreach ($f in $di.EnumerateFiles('*', $opt)) {
    $rel = $f.FullName.Substring($Root.Length).TrimStart('\').Replace('\','/')

    $isDenied = $false
    foreach ($rx in $Rules.Deny) { if ($rel -match $rx) { $isDenied = $true; break } }
    if ($isDenied) { $denied++; continue }

    $isInc = $false
    foreach ($rx in $Rules.Include) { if ($rel -match $rx) { $isInc = $true; break } }
    if (-not $isInc) { continue }

    # CRED gate, pass 1 - on selection
    if (Test-CredentialPath $rel) { $credBlocked++; continue }

    $sel.Add([pscustomobject]@{ Rel = $rel; Full = $f.FullName; Bytes = $f.Length })
  }
  return [pscustomobject]@{ Files = $sel; Denied = $denied; CredBlocked = $credBlocked }
}

function Invoke-Baseline {
  param(
    [Parameter(Mandatory)][string]$Root,
    [Parameter(Mandatory)][string]$Repo,
    [Parameter(Mandatory)][string]$ManifestPath,
    [Parameter(Mandatory)][string]$DestRelative,
    [switch]$Apply,
    [switch]$Quiet
  )
  $result = [pscustomobject]@{
    Ok=$false; Stage=''; Message=''
    Selected=0; Bytes=0L; Copied=0; Denied=0; CredBlocked=0
    IgnoredPaths=@(); CredInDest=@()
  }

  # DEST gate
  $destAbs = [System.IO.Path]::GetFullPath((Join-Path $Repo ($DestRelative -replace '/','\')))
  $repoAbs = [System.IO.Path]::GetFullPath($Repo).TrimEnd('\')
  if (-not $destAbs.StartsWith($repoAbs + '\')) {
    $result.Stage='DEST'; $result.Message="destination '$destAbs' is outside repo root '$repoAbs'"; return $result
  }

  $rules = Read-Manifest -Path $ManifestPath
  $pick  = Select-BaselineFiles -Root $Root -Rules $rules
  $result.Selected    = $pick.Files.Count
  $result.Bytes       = (($pick.Files | Measure-Object -Sum Bytes).Sum)
  if (-not $result.Bytes) { $result.Bytes = 0L }
  $result.Denied      = $pick.Denied
  $result.CredBlocked = $pick.CredBlocked

  if ($pick.Files.Count -eq 0) {
    $result.Stage='SELECT'; $result.Message='manifest selected zero files - refusing to report success'; return $result
  }

  if (-not $Apply) { $result.Ok=$true; $result.Stage='DRYRUN'; $result.Message='selection only'; return $result }

  foreach ($f in $pick.Files) {
    $target = Join-Path $destAbs ($f.Rel -replace '/','\')
    $tdir = [System.IO.Path]::GetDirectoryName($target)
    if (-not (Test-Path -LiteralPath $tdir)) { New-Item -ItemType Directory -Force -Path $tdir | Out-Null }
    Copy-Item -LiteralPath $f.Full -Destination $target -Force
    $result.Copied++
  }

  # CRED gate, pass 2 - sweep the destination we just wrote
  $opt = New-Object System.IO.EnumerationOptions
  $opt.RecurseSubdirectories=$true; $opt.IgnoreInaccessible=$true
  $dd = New-Object System.IO.DirectoryInfo $destAbs
  $credHits = @()
  foreach ($f in $dd.EnumerateFiles('*',$opt)) {
    $rel = $f.FullName.Substring($destAbs.Length).TrimStart('\').Replace('\','/')
    if (Test-CredentialPath $rel) { $credHits += $rel }
  }
  if ($credHits.Count -gt 0) {
    $result.CredInDest = $credHits
    $result.Stage='CRED'; $result.Message="$($credHits.Count) credential-shaped file(s) reached the destination"; return $result
  }

  # IGNORE gate - a backup git ignores is not a backup
  $relForGit = @()
  foreach ($f in $pick.Files) { $relForGit += ($DestRelative.TrimEnd('/') + '/' + $f.Rel) }
  $ignored = @()
  for ($i = 0; $i -lt $relForGit.Count; $i += 200) {
    $chunk = $relForGit[$i..([Math]::Min($i+199, $relForGit.Count-1))]
    $o = @()
    try { $o = @(& git -C $Repo check-ignore -- @chunk 2>$null) } catch {}
    foreach ($line in $o) { if ($line) { $ignored += $line.Trim() } }
  }
  if ($ignored.Count -gt 0) {
    $result.IgnoredPaths = $ignored
    $result.Stage='IGNORE'; $result.Message="$($ignored.Count) copied path(s) are git-ignored - the backup would be invisible"; return $result
  }

  $result.Ok=$true; $result.Stage='DONE'; $result.Message='copied and verified git-visible'
  return $result
}

# ------------------------------------------------------------------------------- self-test
if ($SelfTest) {
  $fail = 0
  $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("baseline_selftest_" + [guid]::NewGuid().ToString('N').Substring(0,8))
  $srcRoot  = Join-Path $tmp 'src'
  $repoRoot = Join-Path $tmp 'repo'
  New-Item -ItemType Directory -Force -Path (Join-Path $srcRoot 'hooks\recall-gate') | Out-Null
  New-Item -ItemType Directory -Force -Path $repoRoot | Out-Null

  'setting=1'      | Set-Content (Join-Path $srcRoot 'settings.json')
  'gate code'      | Set-Content (Join-Path $srcRoot 'hooks\recall-gate\gate.py')
  'SECRET-VALUE'   | Set-Content (Join-Path $srcRoot '.credentials.json')
  'old settings'   | Set-Content (Join-Path $srcRoot 'settings.json.bak-20260101-000000')
  'cache'          | Set-Content (Join-Path $srcRoot 'hooks\recall-gate\gate.pyc')

  & git -C $repoRoot init -q 2>$null
  # mimic the real ~/.agents/.gitignore in the two ways that matter
  @('*credential*','*.bak-*','backups/') | Set-Content (Join-Path $repoRoot '.gitignore')

  $mfGood = Join-Path $tmp 'mf_good.txt'
  @('!**/*credential*','!**/*.bak-*','!**/*.pyc','settings.json','hooks/**') | Set-Content $mfGood

  # a manifest that (wrongly) tries to include the credential file and a .bak
  $mfBad = Join-Path $tmp 'mf_bad.txt'
  @('settings.json','hooks/**','.credentials.json','settings.json.bak-20260101-000000') | Set-Content $mfBad

  Write-Output '=== SELF-TEST 1/5: GOOD manifest -> copies and verifies (MUST pass) ==='
  $r = Invoke-Baseline -Root $srcRoot -Repo $repoRoot -ManifestPath $mfGood -DestRelative 'harness-baseline/dot-claude' -Apply
  $ok = ($r.Ok -and $r.Stage -eq 'DONE' -and $r.Copied -eq 2)
  if (-not $ok) { $fail++ }
  Write-Output ("  [{0}] Ok={1} Stage={2} copied={3} selected={4} denied={5}" -f $(if($ok){'PASS'}else{'FAIL'}),$r.Ok,$r.Stage,$r.Copied,$r.Selected,$r.Denied)

  Write-Output '=== SELF-TEST 2/5: CRED gate - manifest asks for .credentials.json (MUST refuse to copy it) ==='
  $r2 = Invoke-Baseline -Root $srcRoot -Repo $repoRoot -ManifestPath $mfBad -DestRelative 'harness-baseline/dot-claude2' -Apply
  $credLanded = Test-Path (Join-Path $repoRoot 'harness-baseline\dot-claude2\.credentials.json')
  $ok = ((-not $credLanded) -and $r2.CredBlocked -ge 1)
  if (-not $ok) { $fail++ }
  Write-Output ("  [{0}] credential_file_on_disk={1} credBlocked={2} stage={3}" -f $(if($ok){'PASS'}else{'FAIL'}),$credLanded,$r2.CredBlocked,$r2.Stage)

  Write-Output '=== SELF-TEST 3/5: IGNORE gate - a .bak-* slips in -> run MUST fail as git-invisible ==='
  # mfBad includes the .bak file, which git ignores via *.bak-*
  $ok = ((-not $r2.Ok) -and $r2.Stage -eq 'IGNORE')
  if (-not $ok) { $fail++ }
  Write-Output ("  [{0}] Ok={1} Stage={2} ignored_count={3} msg={4}" -f $(if($ok){'PASS'}else{'FAIL'}),$r2.Ok,$r2.Stage,$r2.IgnoredPaths.Count,$r2.Message)

  Write-Output '=== SELF-TEST 4/5: IGNORE gate catches the classic trap - dest under backups/ (MUST fail) ==='
  $r3 = Invoke-Baseline -Root $srcRoot -Repo $repoRoot -ManifestPath $mfGood -DestRelative 'backups/dot-claude' -Apply
  $ok = ((-not $r3.Ok) -and $r3.Stage -eq 'IGNORE')
  if (-not $ok) { $fail++ }
  Write-Output ("  [{0}] Ok={1} Stage={2} ignored_count={3}" -f $(if($ok){'PASS'}else{'FAIL'}),$r3.Ok,$r3.Stage,$r3.IgnoredPaths.Count)

  Write-Output '=== SELF-TEST 5/5: DEST gate - destination outside the repo (MUST refuse) ==='
  $r4 = Invoke-Baseline -Root $srcRoot -Repo $repoRoot -ManifestPath $mfGood -DestRelative '../escape' -Apply
  $ok = ((-not $r4.Ok) -and $r4.Stage -eq 'DEST')
  if (-not $ok) { $fail++ }
  Write-Output ("  [{0}] Ok={1} Stage={2} msg={3}" -f $(if($ok){'PASS'}else{'FAIL'}),$r4.Ok,$r4.Stage,$r4.Message)

  Write-Output '=== SELF-TEST 6/6: REGRESSION - the 2026-09-25 over-block defect ==='
  Write-Output '    A path containing the WORD "credential" but holding SOURCE must be copied;'
  Write-Output '    a real credential store must still be blocked. Both in one run.'
  $cases = @(
    @('hooks/deny-credential-reads/deny.py',              $false, 'guard-hook source'),
    @('hooks/deny-credential-reads/test_deny.py',         $false, 'guard-hook test'),
    @('hooks/deny-credential-reads/README.md',            $false, 'guard-hook doc'),
    @('.credentials.json',                                $true,  'real credential store'),
    @('hooks/x/credentials.json',                         $true,  'nested credential store'),
    @('hooks/x/gh-credentials.json',                      $true,  'prefixed credential store'),
    @('hooks/x/server.pem',                               $true,  'private cert'),
    @('hooks/x/id_ed25519',                               $true,  'ssh private key'),
    @('hooks/x/.env',                                     $true,  'dotenv'),
    @('hooks/x/oauth-token.json',                         $true,  'token store'),
    @('hooks/x/token_helper.py',                          $false, 'source that merely mentions token'),
    @('hooks/x/secrets-doc.md',                           $false, 'doc that merely mentions secret')
  )
  foreach ($c in $cases) {
    $got = Test-CredentialPath $c[0]
    $ok = ($got -eq $c[1])
    if (-not $ok) { $fail++ }
    Write-Output ("  [{0}] blocked={1,-5} expected={2,-5} {3,-45} ({4})" -f $(if($ok){'PASS'}else{'FAIL'}),$got,$c[1],$c[0],$c[2])
  }

  Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
  if ($fail -gt 0) { Write-Output "FAILED:baseline-selftest $fail misclassification(s)"; exit 1 }
  Write-Output 'SUCCESS:baseline-selftest all gates fire on broken input and pass on good input'
  exit 0
}

# ------------------------------------------------------------------------------- main
if (-not $Manifest) { $Manifest = Join-Path $RepoRoot 'harness-baseline\baseline-manifest.txt' }
if (-not (Test-Path -LiteralPath $Manifest))   { Write-Output "FAILED:baseline manifest not found: $Manifest"; exit 1 }
if (-not (Test-Path -LiteralPath $ClaudeRoot)) { Write-Output "FAILED:baseline source not found: $ClaudeRoot"; exit 1 }

Write-Output ("source   = " + $ClaudeRoot)
Write-Output ("repo     = " + $RepoRoot)
Write-Output ("manifest = " + $Manifest)
Write-Output ("dest     = " + $DestRel)
Write-Output ("mode     = " + $(if($DryRun){'DRY-RUN'}else{'APPLY'}))
Write-Output ''

$r = Invoke-Baseline -Root $ClaudeRoot -Repo $RepoRoot -ManifestPath $Manifest -DestRelative $DestRel -Apply:(-not $DryRun)

Write-Output ("selected      = {0} files, {1} bytes ({2} MB)" -f $r.Selected, $r.Bytes, [math]::Round($r.Bytes/1MB,2))
Write-Output ("denied        = {0} (manifest ! rules)" -f $r.Denied)
Write-Output ("cred_blocked  = {0} (CRED gate, selection pass)" -f $r.CredBlocked)
Write-Output ("copied        = {0}" -f $r.Copied)
Write-Output ("stage         = {0}" -f $r.Stage)
Write-Output ("message       = {0}" -f $r.Message)
if ($r.CredInDest.Count -gt 0) {
  Write-Output "--- CREDENTIAL-SHAPED FILES IN DESTINATION (names only, no contents) ---"
  $r.CredInDest | Select-Object -First 20 | ForEach-Object { Write-Output ("  " + $_) }
}
if ($r.IgnoredPaths.Count -gt 0) {
  Write-Output "--- GIT-IGNORED DESTINATION PATHS (first 20) ---"
  $r.IgnoredPaths | Select-Object -First 20 | ForEach-Object { Write-Output ("  " + $_) }
}

if (-not $r.Ok) { Write-Output ("FAILED:baseline " + $r.Stage + " " + $r.Message); exit 1 }
Write-Output ("SUCCESS:baseline " + $r.Stage)
exit 0
