$ErrorActionPreference = 'Stop'
$WW = 'C:\Users\Prekzursil\scripts\world-watch.ps1'
$work = Join-Path $env:TEMP ("ww-test-{0}" -f ([guid]::NewGuid().ToString('N').Substring(0,8)))
New-Item -ItemType Directory -Force -Path $work | Out-Null
$fails = @()
function Check($name,$cond){ if($cond){"PASS: $name"}else{"FAIL: $name"; $script:fails += $name} }
function Entries([string]$f){ if(Test-Path $f){ @(Get-Content $f | Where-Object { $_ -match '^\[\d{4}-' }) } else { @() } }

# ---- deterministic offline cycle via file_hash ----
$watched = Join-Path $work 'watched.bin'
Set-Content -LiteralPath $watched -Value 'v1' -Encoding utf8
$yaml = Join-Path $work 'w.yaml'
@"
watchers:
  - id: testfile
    type: file_hash
    path: $watched
    note: "watched test file changed"
    propose: "inspect the change"
  - id: missingfile
    type: file_hash
    path: C:\does\not\exist\nope.bin
    note: "should always skip"
"@ | Set-Content -LiteralPath $yaml -Encoding utf8

$st = Join-Path $work 'state.json'; $dg = Join-Path $work 'digest.md'; $lg = Join-Path $work 'ww.log'

Write-Output '--- 1. first run = baseline, no fire ---'
& $WW -ConfigFile $yaml -StateFile $st -DigestFile $dg -LogFile $lg
Check 'run1 records state file' (Test-Path $st)
Check 'run1 fires NO digest entry (baseline)' ((@(Entries $dg)).Count -eq 0)
Check 'run1 logs BASE for testfile' ((Get-Content $lg -Raw) -match 'BASE\s+testfile')
Check 'run1 SKIPs the missing-file watcher (fail-open)' ((Get-Content $lg -Raw) -match 'SKIP\s+missingfile')

Write-Output '--- 2. change the file -> run2 fires one digest line ---'
Set-Content -LiteralPath $watched -Value 'v2-different' -Encoding utf8
& $WW -ConfigFile $yaml -StateFile $st -DigestFile $dg -LogFile $lg
$e = @(Entries $dg)
$first = if($e.Count -ge 1){ $e[0] } else { '' }
Check 'run2 fires exactly 1 digest entry' ($e.Count -eq 1)
Check 'entry tagged [world-watch]' ($first -match '\[world-watch\]')
Check 'entry says testfile changed' ($first -match 'testfile changed')
Check 'entry carries PROPOSE' ($first -match 'PROPOSE: inspect the change')

Write-Output '--- 3. no change -> run3 fires nothing more ---'
& $WW -ConfigFile $yaml -StateFile $st -DigestFile $dg -LogFile $lg
Check 'run3 adds no new digest entry' ((@(Entries $dg)).Count -eq 1)
Check 'run3 logs SAME for testfile' ((Get-Content $lg -Raw) -match 'SAME\s+testfile')

Write-Output '--- 4. fail-open: missing config ---'
$threw = $false
try { & $WW -ConfigFile (Join-Path $work 'nope.yaml') -StateFile (Join-Path $work 's4.json') -DigestFile (Join-Path $work 'd4.md') -LogFile (Join-Path $work 'l4.log') } catch { $threw = $true }
Check 'missing config -> no throw' (-not $threw)
Check 'missing config -> logs SKIP, no digest' (((Get-Content (Join-Path $work 'l4.log') -Raw) -match 'SKIP') -and ((@(Entries (Join-Path $work 'd4.md'))).Count -eq 0))

Write-Output '--- 5. fail-open: corrupt YAML ---'
'watchers: [ :: not : valid : yaml ::' | Set-Content -LiteralPath (Join-Path $work 'bad.yaml') -Encoding utf8
$threw = $false
try { & $WW -ConfigFile (Join-Path $work 'bad.yaml') -StateFile (Join-Path $work 's5.json') -DigestFile (Join-Path $work 'd5.md') -LogFile (Join-Path $work 'l5.log') } catch { $threw = $true }
Check 'corrupt YAML -> no throw (fail-open)' (-not $threw)
Check 'corrupt YAML -> no digest entry' ((@(Entries (Join-Path $work 'd5.md'))).Count -eq 0)

Write-Output ''
if ($fails.Count -gt 0) { Write-Output ("FAILED ({0}): {1}" -f $fails.Count, ($fails -join ', ')) }
else { Write-Output 'ALL PASS' }
Write-Output "workdir: $work"
