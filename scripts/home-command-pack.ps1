<#
  home-command-pack.ps1  —  READ-ONLY live-state probe for HOME (desktop-a60s9gp)
  Run in pwsh 7 (verified present at C:\Program Files\PowerShell\7\pwsh.exe).

  WHY THIS EXISTS: the estate's own mcp_ram_audit.ps1 reports 0.00 MB for every
  process (it reads PrivateMemorySize64, which does NOT exist on a Win32_Process
  CIM object) and truncates its grouping key to 4 tokens (collapsing distinct
  servers into one apparent group). So BLOCK 0 proves each instrument against a
  known state BEFORE any number is emitted.

  IT CHANGES NOTHING. No kill, no edit, no task change, no restart.
  Paste back BLOCK 0 + BLOCK A + the anomaly rows from BLOCK C (redacted).
#>
$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'SilentlyContinue'

# NOTE: do NOT name this 'H' - PowerShell aliases 'h' to Get-History and the call silently misbinds.
function Section($t){ "`n=========== $t ===========" }

Section "BLOCK 0 — SELF-TEST (do not trust later blocks if any line says FAIL)"
"pwsh version      : $($PSVersionTable.PSVersion)  (need 6+ for -AsHashtable)"
"elevated          : $([bool](([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)))"
$probe = Get-CimInstance Win32_Process -Filter "ProcessId=$PID"
"PrivatePageCount  : $(if($null -ne $probe.PrivatePageCount){'OK (' + [math]::Round($probe.PrivatePageCount/1MB,1) + ' MB for this shell)'}else{'FAIL - property missing'})"
"PrivateMemorySize64 on CIM : $(if($null -eq $probe.PrivateMemorySize64){'ABSENT (confirms the audit-script bug)'}else{'present'})"
# ancestry self-test on a known chain (this shell -> its parent)
$allProc = Get-CimInstance Win32_Process
$byPid = @{}; foreach($pr in $allProc){ $byPid[[int]$pr.ProcessId] = $pr }
$selfParent = $byPid[[int]$PID].ParentProcessId
"ancestry walk     : $(if($byPid.ContainsKey([int]$selfParent)){'OK (parent ' + $selfParent + ' = ' + $byPid[[int]$selfParent].Name + ')'}else{'FAIL - lookup table broken'})"
try { $null = Get-Content "$HOME\.claude.json" -Raw | ConvertFrom-Json -ErrorAction Stop; "strict ConvertFrom-Json on .claude.json : OK" }
catch { "strict ConvertFrom-Json on .claude.json : FAILS -> $($_.Exception.Message.Split([Environment]::NewLine)[0])" }

Section "BLOCK A — MCP-CLASS PROCESSES (the decisive one: owning-session rollup)"
$mcp = $allProc | Where-Object { $_.Name -match '^(node|python|pythonw|uv|uvx|npx|bun|deno)\.exe$' }
"MCP-class processes : $($mcp.Count)"
"distinct full cmdlines : $(($mcp | Select-Object -Expand CommandLine -Unique | Measure-Object).Count)"
"total private GB    : $([math]::Round((($mcp | Measure-Object -Property PrivatePageCount -Sum).Sum)/1GB,2))   # PrivatePageCount is BYTES, not pages"
"npx-cli wrappers    : $(($mcp | Where-Object { $_.CommandLine -match 'npx-cli\.js' }).Count)   # true wrapper hops"
"procs under _npx    : $(($mcp | Where-Object { $_.CommandLine -match '_npx' }).Count)   # servers resolved from the npx cache"
"`n-- owning session rollup (which live agent owns them) --"
$mcp | ForEach-Object {
    $cur = $_; $hops = 0; $owner = 'UNKNOWN'
    while ($cur -and $hops -lt 12) {
        if ($cur.Name -match '^(claude|codex|cursor|Code|windsurf)\.exe$') { $owner = "SESSION:$($cur.Name):$($cur.ProcessId)"; break }
        # 2026-09-25 fix: without this branch, HOME's task/service-launched daemons all fell
        # through to UNKNOWN (91 of 109) - an instrument gap, not a finding about HOME.
        if ($cur.Name -match '^(services|svchost|taskeng|taskhostw|wininit)\.exe$') { $owner = 'DAEMON(service/task)'; break }
        $pp = [int]$cur.ParentProcessId
        if (-not $byPid.ContainsKey($pp)) { $owner = 'DEAD-PARENT'; break }
        $cur = $byPid[$pp]; $hops++
    }
    [pscustomobject]@{ Owner = $owner }
} | Group-Object Owner | Sort-Object Count -Descending |
    Select-Object @{n='Owner';e={$_.Name}}, Count | Format-Table -Auto | Out-String
"INTERPRET: if counts cluster under a few claude/codex PIDs with few DEAD-PARENT,"
"           HOME has per-session MULTIPLICATION (orphan reapers cannot help)."
"           If DEAD-PARENT dominates, HOME genuinely has orphans (reapers aimed right)."
"`n-- top duplicated command lines (multiplicity) --"
$mcp | Group-Object CommandLine | Sort-Object Count -Descending | Select-Object -First 8 |
    Select-Object Count, @{n='Cmd(tail)';e={ $c=$_.Name; if($c.Length -gt 90){'...'+$c.Substring($c.Length-90)}else{$c} }} |
    Format-Table -Auto | Out-String

Section "BLOCK B — CONSOLE / TERMINAL-SPAM SOURCES"
foreach($sf in @("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup","$env:ProgramData\Microsoft\Windows\Start Menu\Programs\Startup")){
    "-- $sf --"
    Get-ChildItem $sf -ErrorAction SilentlyContinue | Select-Object Name | ForEach-Object { "   $($_.Name)" }
}
"-- tasks running on an INTERACTIVE token (these flash a window) --"
Get-ScheduledTask -ErrorAction SilentlyContinue |
  Where-Object { $_.Principal.LogonType -eq 'Interactive' -and $_.TaskPath -notlike '\Microsoft\*' } |
  Select-Object TaskName, @{n='Repeat';e={$_.Triggers.Repetition.Interval -join ','}} | Format-Table -Auto | Out-String
"-- visible console windows right now --"
Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle } |
  Select-Object Id, ProcessName, MainWindowTitle | Format-Table -Auto | Out-String

Section "BLOCK C — SCHEDULED TASKS (state / last / next / result) + duplicate detection"
$t = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskPath -notlike '\Microsoft\*' }
"non-Microsoft tasks : $($t.Count)"
$rows = foreach($x in $t){
  $i = $x | Get-ScheduledTaskInfo -ErrorAction SilentlyContinue
  [pscustomobject]@{
    Name=$x.TaskName; State=$x.State
    Last=$i.LastRunTime; Next=$i.NextRunTime
    Result=('0x{0:X}' -f $i.LastTaskResult); Missed=$i.NumberOfMissedRuns
    Sup=([bool]($x.TaskName -match 'watchdog|keeper|guard|reap|supervis|monitor|health|hub|mcp'))
  }
}
"supervision-style tasks : $(($rows | Where-Object Sup).Count) of $($rows.Count)"
"`n-- ANOMALIES (never-run, non-zero result, or disabled-but-supervision) --"
$rows | Where-Object { $_.Result -ne '0x0' -or $null -eq $_.Last -or ($_.Sup -and $_.State -eq 'Disabled') } |
  Sort-Object Name | Format-Table -Auto | Out-String
"`n-- NEAR-DUPLICATE task names (e.g. MCP-Orphan-Reaper vs MCPOrphanReaper) --"
$rows | Group-Object { ($_.Name -replace '[^a-zA-Z]','').ToLower() } | Where-Object Count -gt 1 |
  ForEach-Object { "   DUP: " + (($_.Group.Name) -join '  |  ') }

Section "BLOCK D — DECLARED LOOPBACK ENDPOINTS vs ACTUAL LISTENERS"
$listen = (Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue).LocalPort | Sort-Object -Unique
try {
  $cj = Get-Content "$HOME\.claude.json" -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
  $ports = @()
  foreach($kv in $cj.mcpServers.GetEnumerator()){
    $u = $kv.Value.url
    if($u -and $u -match ':(\d{2,5})'){ $ports += [pscustomobject]@{ Server=$kv.Key; Port=[int]$Matches[1] } }
  }
  "declared loopback endpoints : $($ports.Count)  (NOTE: stdio servers have no port; this is not total capability)"
  $ports | Sort-Object Port -Unique | ForEach-Object {
    "   {0,-28} :{1,-6} {2}" -f $_.Server, $_.Port, $(if($listen -contains $_.Port){'LISTENING'}else{'NO-LISTENER'})
  }
} catch { "could not parse .claude.json with -AsHashtable: $($_.Exception.Message.Split([Environment]::NewLine)[0])" }
"-- other control planes present on HOME (Block D only reads .claude.json) --"
foreach($f in '.mcp.json','.mcp-funnel.json','.mcp-presets.json','.mcp.disabled.json','.mcp-disabled-defaults.json'){
  "   {0,-30} {1}" -f $f, (Test-Path "$HOME\$f")
}

Section "BLOCK E — RESTART-LOOP SIGNATURE IN SUPERVISOR LOGS"
$logDir = "$HOME\.agents\logs"
if(Test-Path $logDir){
  # 2026-09-25 fix: -Filter takes ONE string; an array threw and Block E never ran on HOME.
  Get-ChildItem -Path "$logDir\*" -Include '*supervisor*.log','*watchdog*.log','*guard*.log','*keeper*.log' -ErrorAction SilentlyContinue | ForEach-Object {
    $c = Get-Content $_.FullName -ErrorAction SilentlyContinue
    # 2026-09-25 fix: -SimpleMatch treats the alternation as a LITERAL string and matched
    # nothing, reporting restart-ish=0 on a log with 162 relaunches - a silent zero, the
    # exact failure mode this pack exists to prevent. Regex mode, no -SimpleMatch.
    $starts = ($c | Select-String -Pattern 'starting|relaunch|restart|launching').Count
    "   {0,-42} lines={1,-6} restart-ish={2}" -f $_.Name, $c.Count, $starts
  }
} else { "   no $logDir" }
"INTERPRET: many 'starting...' lines with NO root-cause line = restart loop masking a defect,"
"           not healthy self-healing. (VM-side reference: 162 relaunches over ~28 days.)"

Section "REDACTION BEFORE PASTING"
"Block A prints full command lines and this estate has at least one provider key stored as a"
"plaintext literal in a .claude.json env block. Pipe anything you share through:"
'   $out -replace ''(?i)(sk-|hf_|ghp_|github_pat_|glpat-|xox[baprs]-)[A-Za-z0-9_\-]{8,}'', ''<REDACTED>'''
