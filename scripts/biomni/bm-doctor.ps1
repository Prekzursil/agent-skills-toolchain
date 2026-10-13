# bm-doctor - full-stack PASS/WARN/FAIL/NOT-CHECKED report for the Biomni deploy.
# Mirrors cs-doctor discipline: every row states its verdict honestly, NOT-CHECKED
# never renders green, exit code propagates (non-zero on FAIL) so `bm doctor` gates.
# Probe discipline: NO embedded double-quotes inside WSL commands (they terminate
# the bash -lc wrapper); sentinel-delimited parsing; schtasks fallback for the task.
[CmdletBinding()]
param([switch]$Json)
$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'bm-lib.ps1')

$script:Rows = [System.Collections.Generic.List[object]]::new()
function Add-Row {
  param([string]$Name, [ValidateSet('PASS','WARN','FAIL','NOT-CHECKED','INFO')][string]$Status, [string]$Detail = '')
  $script:Rows.Add([pscustomobject]@{ Row = $Name; Status = $Status; Detail = $Detail })
}

# 1. WSL reachable
$echo = Invoke-BMWsl 'echo __WSLUP__' 15
if ($echo -match '__WSLUP__') { Add-Row 'WSL reachable' 'PASS' } else { Add-Row 'WSL reachable' 'FAIL' (Format-BMProbeReply $echo) }

# 2. Daemon health (state + latency, wedge flag)
$h = Test-BMHealth
if ($h.State -eq 'HEALTHY') {
  Add-Row 'biomni-web :7860' 'PASS' ("http={0} latency={1}ms" -f $h.Http, $h.Ms)
} elseif ($h.State -eq 'SLOW') {
  Add-Row 'biomni-web :7860' 'WARN' ("WEDGED http={0} latency={1}ms - run: bm fix" -f $h.Http, $h.Ms)
} else {
  Add-Row 'biomni-web :7860' 'FAIL' 'down - run: bm fix'
}

# 3. Process + disk (sentinel-delimited fields)
$blob = Invoke-BMWsl 'echo __P__; ps aux | grep -ac "[p]ython.*biomni_"; echo __D__; df -BG --output=avail / 2>/dev/null | tail -1 | tr -dc 0-9; echo' 20
if ($blob -eq '__WSL_TIMEOUT__') {
  Add-Row 'daemon detail' 'NOT-CHECKED' 'WSL round-trip timed out'
} else {
  $pm = [regex]::Match($blob, '__P__\s*\r?\n\s*(\d+)')
  $dm = [regex]::Match($blob, '__D__\s*\r?\n\s*(\d+)')
  $n = if ($pm.Success) { [int]$pm.Groups[1].Value } else { 0 }
  Add-Row 'daemon processes' $(if ($n -ge 1) { 'PASS' } else { 'FAIL' }) "procs=$n"
  if ($dm.Success) {
    $diskGb = [int]$dm.Groups[1].Value
    if ($diskGb -lt 10) { Add-Row 'WSL disk free' 'FAIL' "${diskGb}GB < 10GB" }
    else { Add-Row 'WSL disk free' 'PASS' "${diskGb}GB" }
  } else { Add-Row 'WSL disk free' 'NOT-CHECKED' 'disk probe unavailable' }
}

# 4. Environment: conda env + .env (presence + perms only - NEVER values)
$envPerm = Format-BMProbeReply (Invoke-BMWsl 'stat -c %a /home/prekzursil/Biomni/.env 2>/dev/null' 15)
Add-Row '.env present' $(if ($envPerm) { 'PASS' } else { 'FAIL' }) "mode=$envPerm (600 expected)"
$envVars = Format-BMProbeReply (Invoke-BMWsl 'grep -c -e BIOMNI_SOURCE -e BIOMNI_LLM -e BIOMNI_CUSTOM_BASE_URL -e BIOMNI_CUSTOM_API_KEY /home/prekzursil/Biomni/.env 2>/dev/null' 15)
Add-Row '.env vars (4)' $(if ($envVars -eq '4') { 'PASS' } else { 'FAIL' }) "found=$envVars"
$envBin = Format-BMProbeReply (Invoke-BMWsl 'test -x /home/prekzursil/miniforge3/envs/biomni_e1/bin/python && echo yes' 15)
Add-Row 'conda env biomni_e1' $(if ($envBin -eq 'yes') { 'PASS' } else { 'FAIL' }) $envBin

# 5. Data lake (size + completion marker + symlink)
$lake = Format-BMProbeReply (Invoke-BMWsl 'du -sh /home/prekzursil/Biomni/data 2>/dev/null | cut -f1' 60)
Add-Row 'data lake size' $(if ($lake -match '^[0-9]+G$') { 'PASS' } else { 'WARN' }) "$lake (14G expected)"
$lakeDone = Format-BMProbeReply (Invoke-BMWsl 'test -f /home/prekzursil/Biomni/data-lake.DONE && echo yes' 15)
Add-Row 'lake completion marker' $(if ($lakeDone -eq 'yes') { 'PASS' } else { 'NOT-CHECKED' }) 'data-lake.DONE'
$lnk = Format-BMProbeReply (Invoke-BMWsl 'readlink /home/prekzursil/biomni-data 2>/dev/null' 15)
Add-Row 'path symlink' $(if ($lnk -eq '/home/prekzursil/Biomni/data') { 'PASS' } else { 'WARN' }) "biomni-data -> $lnk"

# 6. E1 stack smoke: one CLI tool + one R package (cheap, real)
$plink = Format-BMProbeReply (Invoke-BMWsl 'export PATH=/home/prekzursil/Biomni/biomni_env/biomni_tools/bin:$PATH; plink2 --version 2>/dev/null | head -c 18' 30)
Add-Row 'CLI tools (plink2)' $(if ($plink) { 'PASS' } else { 'FAIL' }) $plink
$lme = Format-BMProbeReply (Invoke-BMWsl 'export PATH=/home/prekzursil/miniforge3/envs/biomni_e1/bin:$PATH; echo Y2F0KHJlcXVpcmUobG1lNCwgcXVpZXRseT1UUlVFKSk= | base64 -d > /tmp/bm_dr.R; Rscript /tmp/bm_dr.R 2>/dev/null' 45)
Add-Row 'R stack (lme4)' $(if ($lme -eq 'TRUE') { 'PASS' } else { 'FAIL' }) "require=$lme"

# 7. Python pins (the two version traps measured 2026-09-20)
$gr = Format-BMProbeReply (Invoke-BMWsl '/home/prekzursil/miniforge3/envs/biomni_e1/bin/pip show gradio 2>/dev/null | sed -n s/^Version://p' 20)
$gr = ($gr -replace '\s', '')
Add-Row 'gradio <6.0 pin' $(if ($gr -match '^5\.') { 'PASS' } elseif ($gr) { 'FAIL' } else { 'NOT-CHECKED' }) $gr
$lg = Format-BMProbeReply (Invoke-BMWsl '/home/prekzursil/miniforge3/envs/biomni_e1/bin/pip show langgraph 2>/dev/null | sed -n s/^Version://p' 20)
$lg = ($lg -replace '\s', '')
Add-Row 'langgraph 1.2.x pin' $(if ($lg -match '^1\.2') { 'PASS' } elseif ($lg) { 'WARN' } else { 'NOT-CHECKED' }) $lg

# 8. Watchdog (registered + running; schtasks fallback - the cmdlet showed
#    registration-lag on this box while the raw store had the task)
$wdState = $null
try { $wdState = (Get-ScheduledTask -TaskName 'BiominiStackGuard' -ErrorAction Stop).State } catch {}
if (-not $wdState) {
  $sq = & schtasks /query /tn BiominiStackGuard /fo csv 2>$null | Select-Object -Last 1
  if ("$sq" -match 'Running|Ready') { $wdState = $Matches[0] }
}
if ($wdState) {
  Add-Row 'watchdog registered' $(if ($wdState -in 'Ready','Running') { 'PASS' } else { 'WARN' }) "state=$wdState"
} else { Add-Row 'watchdog registered' 'WARN' 'no BiominiStackGuard task - run register-bm-tasks.ps1' }

# 9. Host RAM (the freeze root cause on this box)
try {
  $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
  $ramGb = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
  Add-Row 'host free RAM' $(if ($ramGb -lt 3) { 'FAIL' } elseif ($ramGb -lt 6) { 'WARN' } else { 'PASS' }) "${ramGb}GB (wedge risk < 3)"
} catch { Add-Row 'host free RAM' 'NOT-CHECKED' 'CIM unavailable' }

# 10. Slash-command route (does /biomni run this code? - the cs drift lesson)
$cmdFile = Join-Path $HOME '.claude\commands\biomni.md'
if (Test-Path $cmdFile) {
  $names = Select-String -Path $cmdFile -Pattern 'bm\.ps1' -ErrorAction SilentlyContinue
  Add-Row 'slash-command route' $(if ($names) { 'PASS' } else { 'WARN' }) '/biomni references bm.ps1'
} else { Add-Row 'slash-command route' 'NOT-CHECKED' 'no ~/.claude/commands/biomni.md' }

$fail = @($script:Rows | Where-Object Status -eq 'FAIL').Count
$warn = @($script:Rows | Where-Object Status -eq 'WARN').Count
$nc   = @($script:Rows | Where-Object Status -eq 'NOT-CHECKED').Count
$pass = @($script:Rows | Where-Object Status -eq 'PASS').Count

if ($Json) {
  [pscustomobject]@{ rows = $script:Rows; summary = "$fail FAIL, $warn WARN, $nc NOT-CHECKED, $pass PASS" } | ConvertTo-Json -Depth 4
} else {
  foreach ($r in $script:Rows) { '{0,-24} {1,-12} {2}' -f $r.Row, $r.Status, $r.Detail }
  ''
  "summary: $fail FAIL, $warn WARN, $nc NOT-CHECKED, $pass PASS - bm doctor"
}
if ($fail -gt 0) { exit 1 }
if ($nc -gt 0) { exit 2 }
exit 0
