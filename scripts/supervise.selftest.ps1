<#
  BOTH-STATES PROOF for supervise.ps1.

  A supervisor that has never been proven to FIRE is exactly the failure class that left home's
  rclone serve dead for two days. A supervisor that fires on everything is worse. So every
  property is proven in BOTH states: it must ACT on the broken input and REFUSE on the good one.

  Every tick is a SEPARATE pwsh process, so passing these also proves the state is genuinely
  durable across supervisor restarts - nothing load-bearing is held in memory.

  Touches nothing real: a throwaway pwsh test process in a temp WorkDir, no scheduled task, no
  live daemon, no port binding, and the kill guard is exercised against that test process only.
  The test process hard-self-terminates after -MaxSec so it can never outlive the run.

  Run:  pwsh -NoProfile -File supervise.selftest.ps1
  Exit: 0 = all controls passed, 1 = at least one failed.
#>
param(
    [string]$WorkDir,
    [switch]$KeepWorkDir
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Sup = Join-Path $Here 'supervise.ps1'
$Runner = Join-Path $Here 'supervise.selftest\run-sup.ps1'
$TP = Join-Path $Here 'supervise.selftest\testproc.ps1'
$PB = Join-Path $Here 'supervise.selftest\testprobe.ps1'
$ESC = Join-Path $Here 'supervise.selftest\escalate.ps1'
foreach ($f in @($Sup, $Runner, $TP, $PB, $ESC)) {
    if (-not (Test-Path -LiteralPath $f)) { throw "missing required file: $f" }
}

if (-not $WorkDir) { $WorkDir = Join-Path $env:TEMP ('supervise-selftest-' + (Get-Date -Format 'yyyyMMdd-HHmmss')) }
$StateDir = Join-Path $WorkDir 'state'
$EvDir = Join-Path $WorkDir 'ev'
$ParamDir = Join-Path $WorkDir 'params'
foreach ($d in @($StateDir, $EvDir, $ParamDir)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
Write-Host "workdir: $WorkDir`n"

$script:Results = @()
$script:Spawned = @()
$script:Seq = 0

function Add-Result {
    param([string]$Id, [string]$What, [string]$Expect, [string]$Got, [bool]$Pass)
    $script:Results += [pscustomobject]@{ Id = $Id; Pass = $Pass; What = $What }
    Write-Host ("  [{0}] {1,-6} {2}" -f $(if ($Pass) { 'PASS' } else { 'FAIL' }), $Id, $What)
    Write-Host ("           got: {0}" -f $Got)
    if (-not $Pass) { Write-Host ("           EXPECTED: {0}" -f $Expect) }
}

function Invoke-Sup {
    param([hashtable]$P)
    $script:Seq++
    $pf = Join-Path $ParamDir ("p{0:d3}.json" -f $script:Seq)
    ($P | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $pf -Encoding utf8
    $out = & pwsh -NoProfile -File $Runner -ParamFile $pf -Script $Sup 2>&1
    $code = $LASTEXITCODE
    $text = ($out | ForEach-Object { [string]$_ }) -join "`n"
    $m = [regex]::Match($text, 'SUCCESS:supervise/(\S+)\s+verdict=(\S+)\s+action=(\S+)\s+churnTotal=(\d+)')
    [pscustomobject]@{
        Exit    = $code
        Text    = $text
        Verdict = $(if ($m.Success) { $m.Groups[2].Value } else { '' })
        Action  = $(if ($m.Success) { $m.Groups[3].Value } else { '' })
        Churn   = $(if ($m.Success) { [int]$m.Groups[4].Value } else { -1 })
    }
}

function Read-St { param([string]$N) Get-Content -LiteralPath (Join-Path $StateDir "$N.json") -Raw -Encoding utf8 | ConvertFrom-Json }
function Read-UnitPid { param([string]$P) if (Test-Path -LiteralPath $P) { [int]((Get-Content -LiteralPath $P -Raw).Trim()) } else { 0 } }
function Test-Alive { param([int]$Q) if ($Q -le 0) { return $false } [bool](Get-Process -Id $Q -ErrorAction SilentlyContinue) }
function Get-Txt { param([string]$P) if (Test-Path -LiteralPath $P) { Get-Content -LiteralPath $P -Raw } else { '' } }
function Measure-Lines { param([string]$T) @($T -split "`r?`n" | Where-Object { $_ -and $_.Trim() }).Count }

function New-UnitParams {
    param(
        [string]$N, [switch]$Mute, [int]$ExitAfterSec = 0, [string]$ForceExit,
        [string]$Protected = '^(claude|node|python)$',
        [int]$Warmup = 3, [int]$Strikes = 3, [int]$MaxR = 5, [int]$Base = 50, [int]$Cap = 200
    )
    $pidF = Join-Path $WorkDir "$N.pid"
    $hbF = Join-Path $WorkDir "$N.hb"
    $logF = Join-Path $WorkDir "$N.log"
    if (-not (Test-Path -LiteralPath $logF)) {
        Set-Content -LiteralPath $logF -Value "unit $N synthetic log`nsecond line`nthird line" -Encoding utf8
    }
    $sa = @('-NoProfile', '-File', $TP, '-PidFile', $pidF, '-HeartbeatFile', $hbF)
    if ($Mute) { $sa += '-Mute' }
    if ($ExitAfterSec -gt 0) { $sa += @('-ExitAfterSec', [string]$ExitAfterSec) }
    $ra = @('-NoProfile', '-File', $PB, '-HeartbeatFile', $hbF)
    if ($ForceExit) { $ra += @('-ForceExit', $ForceExit) }
    @{
        Name = $N; Once = $true
        StateRoot = $StateDir; EvidenceRoot = $EvDir
        PidFile = $pidF; ProcessNameMatch = '^pwsh$'; ProtectedNameMatch = $Protected
        StartCommand = 'pwsh'; StartArgs = $sa
        ReadinessCommand = 'pwsh'; ReadinessArgs = $ra
        LogFile = $logF; LogTailLines = 50
        WarmupGraceSec = $Warmup; SelfFaultStrikes = $Strikes
        MaxRestarts = $MaxR; WindowSec = 900
        BackoffBaseMs = $Base; BackoffCapMs = $Cap
        _pidFile = $pidF   # harness-only; stripped before dispatch
    }
}
function Get-Dispatch { param([hashtable]$P) $c = @{}; foreach ($k in $P.Keys) { if (-not $k.StartsWith('_')) { $c[$k] = $P[$k] } }; $c }

# ======================================================================================
Write-Host 'C1  LIVENESS - restarts a deliberately-killed process (must FIRE)'
# ======================================================================================
$u = New-UnitParams -N 't-live'
$r1 = Invoke-Sup (Get-Dispatch $u)
Start-Sleep -Seconds 2
$pid1 = Read-UnitPid $u._pidFile
$script:Spawned += $pid1
Add-Result 'C1.1' 'first tick starts the unit' 'verdict=DEAD action=restarted churn=1 pid alive' `
    "verdict=$($r1.Verdict) action=$($r1.Action) churn=$($r1.Churn) pid=$pid1 alive=$(Test-Alive $pid1)" `
    ($r1.Verdict -eq 'DEAD' -and $r1.Action -eq 'restarted' -and $r1.Churn -eq 1 -and (Test-Alive $pid1))

$rH = Invoke-Sup (Get-Dispatch $u)
Add-Result 'C1.2' 'a HEALTHY unit is left alone (control for C1.3)' 'verdict=HEALTHY action=none churn=1 same pid' `
    "verdict=$($rH.Verdict) action=$($rH.Action) churn=$($rH.Churn) samePid=$((Read-UnitPid $u._pidFile) -eq $pid1)" `
    ($rH.Verdict -eq 'HEALTHY' -and $rH.Action -eq 'none' -and $rH.Churn -eq 1 -and (Read-UnitPid $u._pidFile) -eq $pid1)

Stop-Process -Id $pid1 -Force            # <<< the deliberate kill
Start-Sleep -Milliseconds 800
$r2 = Invoke-Sup (Get-Dispatch $u)
Start-Sleep -Seconds 2
$pid2 = Read-UnitPid $u._pidFile
$script:Spawned += $pid2
Add-Result 'C1.3' 'a KILLED unit is restarted with a NEW pid' 'verdict=DEAD action=restarted churn=2 newPid!=oldPid' `
    "verdict=$($r2.Verdict) action=$($r2.Action) churn=$($r2.Churn) old=$pid1 new=$pid2 alive=$(Test-Alive $pid2)" `
    ($r2.Verdict -eq 'DEAD' -and $r2.Action -eq 'restarted' -and $r2.Churn -eq 2 -and $pid2 -ne $pid1 -and (Test-Alive $pid2))
try { Stop-Process -Id $pid2 -Force -ErrorAction SilentlyContinue } catch { }

# ======================================================================================
Write-Host "`nC2  READINESS - refuses to restart an ALIVE-but-mute process (must NOT fire)"
# ======================================================================================
$um = New-UnitParams -N 't-mute' -Mute -Warmup 3
[void](Invoke-Sup (Get-Dispatch $um))
Start-Sleep -Seconds 5                   # heartbeat never written => stale; warmup expires
$mpid = Read-UnitPid $um._pidFile
$script:Spawned += $mpid
$m2 = Invoke-Sup (Get-Dispatch $um)
$stM = Read-St 't-mute'
$sameM = (Read-UnitPid $um._pidFile) -eq $mpid
Add-Result 'C2.1' 'mute-but-alive => DEGRADED-DEPENDENCY and NO restart' 'action=no-restart churn=1 same pid still alive' `
    "verdict=$($m2.Verdict) action=$($m2.Action) churn=$($m2.Churn) samePid=$sameM alive=$(Test-Alive $mpid)" `
    ($m2.Verdict -eq 'DEGRADED-DEPENDENCY' -and $m2.Action -eq 'no-restart' -and $m2.Churn -eq 1 -and $sameM -and (Test-Alive $mpid))
Add-Result 'C2.2' 'the refusal is by POLICY, not by the kill guard' 'state.ownPid == live pid, so a kill WAS permitted' `
    "ownPid=$($stM.ownPid) livePid=$mpid" ([int]$stM.ownPid -eq $mpid)
$nM = Get-Txt (Join-Path $StateDir 't-mute.notify.log')
Add-Result 'C2.3' 'the refusal is NOT silent - it notifies' 'notify log names DEGRADED-DEPENDENCY' `
    "notifyLines=$(Measure-Lines $nM) match=$($nM -match 'DEGRADED-DEPENDENCY')" ($nM -match 'DEGRADED-DEPENDENCY')
try { Stop-Process -Id $mpid -Force -ErrorAction SilentlyContinue } catch { }

$uu = New-UnitParams -N 't-unk' -ForceExit '42' -Warmup 0
[void](Invoke-Sup (Get-Dispatch $uu))
Start-Sleep -Seconds 2
$kpid = Read-UnitPid $uu._pidFile
$script:Spawned += $kpid
$k2 = Invoke-Sup (Get-Dispatch $uu)
Add-Result 'C2.4' 'UNKNOWN readiness (probe exit 42) never restarts' 'verdict=DEGRADED-UNKNOWN action=no-restart churn=1' `
    "verdict=$($k2.Verdict) action=$($k2.Action) churn=$($k2.Churn) alive=$(Test-Alive $kpid)" `
    ($k2.Verdict -eq 'DEGRADED-UNKNOWN' -and $k2.Action -eq 'no-restart' -and $k2.Churn -eq 1 -and (Test-Alive $kpid))
try { Stop-Process -Id $kpid -Force -ErrorAction SilentlyContinue } catch { }

# requirement (a) says "never restart on a dependency OR WARMUP failure" - the warmup half
$uw = New-UnitParams -N 't-warm' -Mute -Warmup 600 -Strikes 1
[void](Invoke-Sup (Get-Dispatch $uw))
Start-Sleep -Seconds 2
$wpid = Read-UnitPid $uw._pidFile
$script:Spawned += $wpid
$w2 = Invoke-Sup (Get-Dispatch $uw)
Add-Result 'C2.5' 'a not-ready unit INSIDE the warmup grace is WARMING, not restarted' 'verdict=WARMING action=no-restart churn=1 same pid alive' `
    "verdict=$($w2.Verdict) action=$($w2.Action) churn=$($w2.Churn) samePid=$((Read-UnitPid $uw._pidFile) -eq $wpid) alive=$(Test-Alive $wpid)" `
    ($w2.Verdict -eq 'WARMING' -and $w2.Action -eq 'no-restart' -and $w2.Churn -eq 1 -and (Read-UnitPid $uw._pidFile) -eq $wpid -and (Test-Alive $wpid))
try { Stop-Process -Id $wpid -Force -ErrorAction SilentlyContinue } catch { }

# ======================================================================================
Write-Host "`nC3  SELF-FAULT - restarts ONLY on sustained positive evidence (both states)"
# ======================================================================================
$us = New-UnitParams -N 't-self' -ForceExit '1' -Warmup 0 -Strikes 3 -MaxR 9
[void](Invoke-Sup (Get-Dispatch $us))
Start-Sleep -Seconds 2
$spid = Read-UnitPid $us._pidFile
$script:Spawned += $spid
$s2 = Invoke-Sup (Get-Dispatch $us)     # strike 1
$s3 = Invoke-Sup (Get-Dispatch $us)     # strike 2
Add-Result 'C3.1' 'SELF-FAULT below the strike threshold does NOT restart' 'both ticks action=no-restart, churn stays 1' `
    "t2=$($s2.Verdict)/$($s2.Action) t3=$($s3.Verdict)/$($s3.Action) churn=$($s3.Churn)" `
    ($s2.Action -eq 'no-restart' -and $s3.Action -eq 'no-restart' -and $s2.Verdict -eq 'SELF-FAULT-PENDING' -and $s3.Churn -eq 1)
$s4 = Invoke-Sup (Get-Dispatch $us)     # strike 3 => WEDGED => restart
Start-Sleep -Seconds 2
$spid2 = Read-UnitPid $us._pidFile
$script:Spawned += $spid2
Add-Result 'C3.2' 'SELF-FAULT at the threshold DOES restart' 'verdict=WEDGED action=restarted churn=2 newPid' `
    "verdict=$($s4.Verdict) action=$($s4.Action) churn=$($s4.Churn) old=$spid new=$spid2" `
    ($s4.Verdict -eq 'WEDGED' -and $s4.Action -eq 'restarted' -and $s4.Churn -eq 2 -and $spid2 -ne $spid)

# ======================================================================================
Write-Host "`nC4  EVIDENCE captured BEFORE the kill"
# ======================================================================================
$evW = Get-ChildItem -Path (Join-Path $EvDir 't-self') -Recurse -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match 'WEDGED$' } | Sort-Object CreationTime | Select-Object -Last 1
$ok4 = $false; $got4 = 'no WEDGED evidence dir found'
if ($evW) {
    $pj = Join-Path $evW.FullName 'process.json'
    if (Test-Path -LiteralPath $pj) {
        $o = Get-Content -LiteralPath $pj -Raw | ConvertFrom-Json
        $names = $o.PSObject.Properties.Name
        $hasCmd = ($names -contains 'commandLine') -and ("$($o.commandLine)" -match 'testproc\.ps1')
        $hasRss = ($names -contains 'workingSet64') -and ([long]$o.workingSet64 -gt 0)
        $pidMatch = [int]$o.pid -eq $spid
        $deadNow = -not (Test-Alive $spid)
        $filesOk = (Test-Path (Join-Path $evW.FullName 'context.json')) -and (Test-Path (Join-Path $evW.FullName 'log.tail')) -and (Test-Path (Join-Path $evW.FullName 'ports.txt'))
        $ok4 = $hasCmd -and $hasRss -and $pidMatch -and $deadNow -and $filesOk
        $got4 = "dir=$($evW.Name) pid=$($o.pid) pidMatch=$pidMatch cmdlineCaptured=$hasCmd rss=$($o.workingSet64) targetDeadNow=$deadNow allFiles=$filesOk"
    }
}
Add-Result 'C4.1' 'cmdline+RSS of the KILLED pid are on disk (only possible pre-kill)' `
    'process.json holds the killed pid, its cmdline and RSS>0; that pid is now dead' $got4 $ok4
try { Stop-Process -Id $spid2 -Force -ErrorAction SilentlyContinue } catch { }

# ======================================================================================
Write-Host "`nC5  KILL GUARD - refuses a protected process, allows a non-protected one"
# ======================================================================================
$ug = New-UnitParams -N 't-guard' -ForceExit '1' -Warmup 0 -Strikes 1 -MaxR 9 -Protected '^pwsh$'
[void](Invoke-Sup (Get-Dispatch $ug))
Start-Sleep -Seconds 2
$gpid = Read-UnitPid $ug._pidFile
$script:Spawned += $gpid
$g2 = Invoke-Sup (Get-Dispatch $ug)
Add-Result 'C5.1' 'protected process name => stop REFUSED, process survives' 'action=stop-refused churn=1 pid alive' `
    "verdict=$($g2.Verdict) action=$($g2.Action) churn=$($g2.Churn) alive=$(Test-Alive $gpid)" `
    ($g2.Action -eq 'stop-refused' -and $g2.Churn -eq 1 -and (Test-Alive $gpid))
$ug2 = New-UnitParams -N 't-guard' -ForceExit '1' -Warmup 0 -Strikes 1 -MaxR 9 -Protected '^(claude|node)$'
$g3 = Invoke-Sup (Get-Dispatch $ug2)
Start-Sleep -Seconds 2
$gpid2 = Read-UnitPid $ug2._pidFile
$script:Spawned += $gpid2
Add-Result 'C5.2' 'non-protected name => stop ALLOWED, unit restarted' 'action=restarted churn=2 newPid' `
    "verdict=$($g3.Verdict) action=$($g3.Action) churn=$($g3.Churn) old=$gpid new=$gpid2" `
    ($g3.Action -eq 'restarted' -and $g3.Churn -eq 2 -and $gpid2 -ne $gpid)
try { Stop-Process -Id $gpid2 -Force -ErrorAction SilentlyContinue } catch { }

# ======================================================================================
Write-Host "`nC6  LATCH - budget exhausted => stop restarting, ESCALATE, and KEEP NOTIFYING"
# ======================================================================================
$marker = Join-Path $WorkDir 'escalated.txt'
$ul = New-UnitParams -N 't-latch' -ExitAfterSec 1 -Warmup 0 -MaxR 2 -Base 50 -Cap 100
$ul['LatchRenotifySec'] = 0
$ul['EscalateCommand'] = 'pwsh'
$ul['EscalateArgs'] = @('-NoProfile', '-File', $ESC, '-MarkerFile', $marker)
$l1 = Invoke-Sup (Get-Dispatch $ul); Start-Sleep -Seconds 3
$l2 = Invoke-Sup (Get-Dispatch $ul); Start-Sleep -Seconds 3
Add-Result 'C6.1' 'restarts INSIDE the budget are permitted (control)' 'two ticks action=restarted, churn=2' `
    "t1=$($l1.Action) t2=$($l2.Action) churn=$($l2.Churn)" `
    ($l1.Action -eq 'restarted' -and $l2.Action -eq 'restarted' -and $l2.Churn -eq 2)
$l3 = Invoke-Sup (Get-Dispatch $ul)
$stL = Read-St 't-latch'
$nlogL = Join-Path $StateDir 't-latch.notify.log'
$nT1 = Get-Txt $nlogL
# Escalation is dispatched ASYNCHRONOUSLY on purpose - a supervisor must never block on a pager.
# Measured: the marker landed ~680ms after "escalation dispatched" was logged, so reading it
# immediately failed the control for a race in the TEST, not a defect in the supervisor.
$escT = ''
for ($i = 0; $i -lt 40; $i++) { $escT = Get-Txt $marker; if ($escT -match 'ESCALATED') { break }; Start-Sleep -Milliseconds 250 }
$latchEv = @(Get-ChildItem -Path (Join-Path $EvDir 't-latch') -Recurse -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match 'latch$' })
Add-Result 'C6.2' 'the restart that would BUST the budget latches instead of thrashing' 'action=latched exit=3 state.latched=true churn stays 2' `
    "action=$($l3.Action) exit=$($l3.Exit) latched=$($stL.latched) churn=$($l3.Churn) reason=$($stL.latchReason)" `
    ($l3.Action -eq 'latched' -and $l3.Exit -eq 3 -and $stL.latched -eq $true -and $l3.Churn -eq 2)
Add-Result 'C6.3' 'the latch ESCALATES to a DIFFERENT remediation' 'escalation marker written' `
    "marker=$(($escT -split "`r?`n" | Where-Object { $_ } | Select-Object -First 1))" ($escT -match 'ESCALATED')
Add-Result 'C6.4' 'the latch NOTIFIES (not a silent stop)' 'notify log names LATCH and the budget reason' `
    "notifyLines=$(Measure-Lines $nT1) hasLATCH=$($nT1 -match 'LATCH') hasReason=$($nT1 -match 'restart budget exhausted')" `
    (($nT1 -match 'LATCH') -and ($nT1 -match 'restart budget exhausted'))
Add-Result 'C6.5' 'the latch captures evidence too' 'an evidence dir named *-latch exists' `
    "latchEvidenceDirs=$($latchEv.Count)" ($latchEv.Count -ge 1)
Start-Sleep -Seconds 3   # let the unit die again, so this tick is a genuine restart candidate
$l4 = Invoke-Sup (Get-Dispatch $ul)
$nT2 = Get-Txt $nlogL
$c1 = Measure-Lines $nT1; $c2 = Measure-Lines $nT2
Add-Result 'C6.6' 'a LATCHED unit keeps talking (the exact rclone-serve failure mode)' 'action=latched-refused AND a new notify line' `
    "action=$($l4.Action) notifyLines $c1 -> $c2 hasLATCHED=$($nT2 -match 'LATCHED')" `
    ($l4.Action -eq 'latched-refused' -and $c2 -gt $c1 -and ($nT2 -match 'LATCHED'))

# ======================================================================================
Write-Host "`nC7  DURABILITY - the latch survives a FRESH supervisor process"
# ======================================================================================
$base7 = @{ Name = 't-latch'; StateRoot = $StateDir; EvidenceRoot = $EvDir; MaxRestarts = 2 }
$sv = Invoke-Sup ($base7 + @{ Status = $true })
Add-Result 'C7.1' 'a brand-new process still sees the latch' 'exit=3 and output says latched=True' `
    "exit=$($sv.Exit) line=$(($sv.Text -split "`r?`n" | Where-Object { $_ -match 'supervise/' } | Select-Object -Last 1))" `
    ($sv.Exit -eq 3 -and $sv.Text -match 'latched=True')
$cl = Invoke-Sup ($base7 + @{ ClearLatch = $true })
$sv2 = Invoke-Sup ($base7 + @{ Status = $true })
Add-Result 'C7.2' '-ClearLatch is the only way out, and it works' 'clear exit=0 then status exit=0 latched=False' `
    "clearExit=$($cl.Exit) statusExit=$($sv2.Exit) latchedFalse=$($sv2.Text -match 'latched=False')" `
    ($cl.Exit -eq 0 -and $sv2.Exit -eq 0 -and $sv2.Text -match 'latched=False')
$churnF = Join-Path $StateDir 't-latch.churn'
Add-Result 'C7.3' 'churn is operator-visible as a bare integer' 'churn file reads 2' `
    "churnFile=$(if (Test-Path $churnF) { (Get-Content $churnF -Raw).Trim() } else { 'MISSING' })" `
    ((Test-Path -LiteralPath $churnF) -and ((Get-Content -LiteralPath $churnF -Raw).Trim() -eq '2'))

# ======================================================================================
Write-Host "`nC8  BACKOFF - exponential, capped, full-jitter (observed, not asserted)"
# ======================================================================================
function Get-Backoffs {
    param([string]$N)
    $lg = Join-Path $StateDir "$N.events.log"
    $o = @()
    if (Test-Path -LiteralPath $lg) {
        foreach ($ln in (Get-Content -LiteralPath $lg)) {
            $mm = [regex]::Match($ln, 'backoff attempt=(\d+) ceiling=(\d+)ms jittered=(\d+)ms')
            if ($mm.Success) { $o += [pscustomobject]@{ A = [int]$mm.Groups[1].Value; C = [int]$mm.Groups[2].Value; J = [int]$mm.Groups[3].Value } }
        }
    }
    # NOT `, $o` - that wraps the array so the caller's @(...) sees exactly ONE object. That is
    # the same defect this harness found in supervise.ps1's Get-SupWindowRestarts, and it was
    # present here too: C8.1 "passed" only because $_.C on the wrapped array happened to
    # member-enumerate into the right five values, while C8.2 crashed comparing 97 to
    # "100 200 400 400 400". Emit the array plainly; call sites wrap with @().
    $o
}
function New-DryParams { param([string]$N, [Nullable[int]]$Seed)
    $h = @{ Name = $N; Once = $true; DryRun = $true; StateRoot = $StateDir; EvidenceRoot = $EvDir
        StartCommand = 'pwsh'; MaxRestarts = 99; WindowSec = 900; BackoffBaseMs = 100; BackoffCapMs = 400
    }
    if ($null -ne $Seed) { $h['JitterSeed'] = [int]$Seed }
    $h
}
1..5 | ForEach-Object { [void](Invoke-Sup (New-DryParams -N 't-bo')) }
$bo = @(Get-Backoffs 't-bo')
$ceils = @($bo | Select-Object -First 5 | ForEach-Object { $_.C })
$expect = @(100, 200, 400, 400, 400)
$ceilOk = ($ceils.Count -eq 5) -and (0 -eq @(Compare-Object $ceils $expect -SyncWindow 0).Count)
Add-Result 'C8.1' 'the ceiling doubles then CAPS' 'ceilings = 100,200,400,400,400' "ceilings = $($ceils -join ',')" $ceilOk
$outOfBand = @($bo | Where-Object { $_.J -lt 0 -or $_.J -gt $_.C }).Count
Add-Result 'C8.2' 'every delay lies in [0, ceiling] - the full-jitter band' 'zero samples outside the band' `
    "samples=$($bo.Count) outOfBand=$outOfBand J=$(($bo | ForEach-Object { $_.J }) -join ',')" `
    ($bo.Count -ge 5 -and $outOfBand -eq 0)
Add-Result 'C8.3' 'jitter is really applied (not always the ceiling)' 'at least one J strictly < its ceiling' `
    "strictlyBelow=$(@($bo | Where-Object { $_.J -lt $_.C }).Count)/$($bo.Count)" `
    (@($bo | Where-Object { $_.J -lt $_.C }).Count -ge 1)
1..3 | ForEach-Object { [void](Invoke-Sup (New-DryParams -N 't-bo-s1' -Seed 7)) }
1..3 | ForEach-Object { [void](Invoke-Sup (New-DryParams -N 't-bo-s2' -Seed 7)) }
1..3 | ForEach-Object { [void](Invoke-Sup (New-DryParams -N 't-bo-u1')) }
$q1 = (@(Get-Backoffs 't-bo-s1') | ForEach-Object { $_.J }) -join ','
$q2 = (@(Get-Backoffs 't-bo-s2') | ForEach-Object { $_.J }) -join ','
$qu = (@(Get-Backoffs 't-bo-u1') | ForEach-Object { $_.J }) -join ','
Add-Result 'C8.4' 'seeded jitter reproduces; unseeded does not repeat it' 'seed7 == seed7 AND unseeded != seed7' `
    "seed7a=[$q1] seed7b=[$q2] unseeded=[$qu]" ($q1 -ne '' -and $q1 -eq $q2 -and $qu -ne $q1)

# ======================================================================================
foreach ($q in $script:Spawned) { try { Stop-Process -Id $q -Force -ErrorAction SilentlyContinue } catch { } }
Write-Host "`n================ RESULTS ================"
$script:Results | Format-Table -AutoSize Id, Pass, What | Out-String -Width 170 | Write-Host
$fail = @($script:Results | Where-Object { -not $_.Pass })
$total = @($script:Results).Count
Write-Host ("controls: {0}  passed: {1}  failed: {2}" -f $total, ($total - $fail.Count), $fail.Count)
Write-Host "workdir kept for inspection: $WorkDir"
if ($fail.Count -eq 0) { Write-Host "SUCCESS:supervise-selftest $total/$total"; exit 0 }
Write-Host ("FAILED:supervise-selftest {0}/{1} failed=[{2}]" -f $fail.Count, $total, (($fail | ForEach-Object { $_.Id }) -join ','))
exit 1
