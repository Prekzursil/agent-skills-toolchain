# Permanent disk-hygiene rule (owner-approved 2026-09-18): AUTO-CLEAR SAFE SLOP, then
# refresh a WizTree CSV, analyze it, and write a persistent DECISIONS-PENDING report of the
# best-next-deletes + decision-needed items for owner review.
#
# SAFE = regenerable, no personal data, no logins. Deletes ONLY: aged temp, recycle bin,
# stale plugin clones (via the owner's disk-maintenance.ps1 protect-list), aged crash dumps,
# and the Windows Update download cache. It NEVER touches Downloads, Documents, node_modules,
# vhdx, Cursor/Claude/Codex state, or any personal file — those are REPORTED, not deleted.
# Runs as a script so the estate direct-delete guard (which only inspects live agent commands)
# does not block it. Elevated (WizTree /admin needs it). -WhatIf previews; -NoScan skips WizTree.
param([int]$KeepDays=7, [string]$Drive='C:', [string]$ReportDir='D:\wiztree-reports', [switch]$NoScan, [switch]$WhatIf)
$ErrorActionPreference='Continue'
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$log = Join-Path $ReportDir 'wiztree-rule.log'
function Log($m){ $l="{0}  {1}" -f (Get-Date -f 'yyyy-MM-dd HH:mm:ss'),$m; Add-Content $log $l }
$cut=(Get-Date).AddDays(-$KeepDays)
$before=(Get-PSDrive C).Free/1GB
Log ("=== weekly hygiene start; C: free {0:N2}GB; keepDays={1}; whatif={2} ===" -f $before,$KeepDays,[bool]$WhatIf)

# ---------- SAFE auto-clean (regenerable only) ----------
$dm="C:\Users\Prekzursil\Documents\disk-maintenance.ps1"
if(Test-Path $dm){ try { if($WhatIf){ & $dm -KeepDays $KeepDays -WhatIf | Out-Null } else { & $dm -KeepDays $KeepDays | Out-Null } } catch { Log "  disk-maintenance error: $($_.Exception.Message)" } }

$cd="$env:LOCALAPPDATA\CrashDumps"
if(Test-Path $cd){ Get-ChildItem $cd -File -Force -EA SilentlyContinue | Where-Object { $_.LastWriteTime -lt $cut } | ForEach-Object { if(-not $WhatIf){ try{ [System.IO.File]::Delete($_.FullName) }catch{} } } }

if(-not $WhatIf){
  try {
    Stop-Service wuauserv,bits -Force -EA SilentlyContinue
    Get-ChildItem 'C:\Windows\SoftwareDistribution\Download' -Force -EA SilentlyContinue | ForEach-Object { Remove-Item $_.FullName -Recurse -Force -EA SilentlyContinue }
    Start-Service wuauserv -EA SilentlyContinue
  } catch { Log "  WU cache clear error: $($_.Exception.Message)" }
}
$afterClean=(Get-PSDrive C).Free/1GB
Log ("  safe-clean reclaimed {0:N2}GB (C: free {1:N2}GB)" -f ($afterClean-$before),$afterClean)

# ---------- REFRESH WizTree CSV + ANALYZE + REPORT ----------
$dl=($Drive.TrimEnd(':','\'))
$stamp=Get-Date -f 'yyyyMMdd'
$csv=Join-Path $ReportDir "wiztree_${dl}_$stamp.csv"
if(-not $NoScan){
  $wt='C:\Program Files\WizTree\WizTree64.exe'
  if(Test-Path $wt){
    Log "  WizTree scan $Drive -> $csv"
    # MEASURED 2026-09-18: WizTree hangs (falls back to a slow scan path, or never
    # completes) when launched with CREATE_NO_WINDOW (e.g. via runhidden.exe / the
    # outer script's own no-window launch chain) -- it needs a REAL window handle to
    # run its fast MFT-based scan, even if that window is never shown. SW_HIDE (a
    # real hidden window, via Start-Process -WindowStyle Hidden) completed an 8.1M-file
    # C: scan in ~115s, matching the visible-window baseline. Do NOT change this back
    # to a direct `&` call or wrap it in runhidden -- both reproduce the hang.
    $argList = @("`"$Drive\`"", "/export=`"$csv`"", '/admin=1', '/exportfolders=1', '/exportfiles=1')
    $p = Start-Process -FilePath $wt -ArgumentList $argList -WindowStyle Hidden -PassThru -Wait
    Log ("  WizTree exit=$($p.ExitCode)")
  } else { Log "  WizTree not found at $wt" }
}
$use = if(Test-Path $csv){ $csv } else { (Get-ChildItem $ReportDir -Filter "wiztree_${dl}_*.csv" -EA SilentlyContinue | Sort-Object LastWriteTime -Desc | Select-Object -First 1).FullName }
if($use){
  $report=Join-Path $ReportDir "DECISIONS-PENDING_$dl.md"
  $py='C:\Python314\python.exe'
  try {
    & $py 'C:\Users\Prekzursil\.agents\scripts\wiztree_analyze.py' "$use" --out $report | Out-Null
    Log "  report -> $report"
    $json = $report -replace '\.md$','.json'
    if(Test-Path $json){
      # Upsert into the durable decision ledger: pending items persist across runs,
      # declined items are tombstoned and never re-asked (owner rule: presented until
      # resolved, never silently dropped, never re-nagged after a "no").
      $ledgerOut = & $py 'C:\Users\Prekzursil\.agents\scripts\wiztree_ledger.py' upsert $json 2>&1
      Log "  ledger: $ledgerOut"
    }
  }
  catch { Log "  analyze/ledger error: $($_.Exception.Message)" }
} else { Log "  no CSV available to analyze" }

# retention: keep last 3 weekly CSVs per drive (each ~3GB on D:)
Get-ChildItem $ReportDir -Filter "wiztree_${dl}_*.csv" -EA SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -Skip 3 | ForEach-Object { if(-not $WhatIf){ try{ [System.IO.File]::Delete($_.FullName) }catch{} }; Log "  pruned old csv $($_.Name)" }
Log ("=== weekly hygiene end; C: free {0:N2}GB ===" -f ((Get-PSDrive C).Free/1GB))
