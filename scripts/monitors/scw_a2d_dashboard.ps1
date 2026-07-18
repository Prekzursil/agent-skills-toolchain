param(
  [string]$IP      = "51.159.182.130",
  [int]$RefreshSec = 8,
  [switch]$Once
)
# Live Scaleway H100x4 dashboard (verbose, accurate) -- phenibut a2d:
#   BPMD ladder (per-trial via out.tgz, MEASURED ETA) + QM interaction-energy jobs
#   (correct done/running/FAILED states via _qm_results.log + live .out/.log).
# Data: ssh <box> bash /root/mon_collect_a2d.sh  (key=value).
#   powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Prekzursil\.biomni-mcp\scw_a2d_dashboard.ps1"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$FULL=[char]0x2588; $EMPTY=[char]0x2591; $CHK=[char]0x2588; $CUR=[char]0x25B6; $PEND=[char]0x00B7; $X=[char]0x2717
$SPARK=@(0x2581,0x2582,0x2583,0x2584,0x2585,0x2586,0x2587,0x2588)|ForEach-Object{[char]$_}

function Bar([double]$pct,[int]$w=18){ if($pct-lt0){$pct=0}; if($pct-gt100){$pct=100}
  $n=[int][math]::Round($w*$pct/100.0); ($FULL.ToString()*$n)+($EMPTY.ToString()*($w-$n)) }
function HMS([double]$s){ if($s-lt0){$s=0}; $t=[timespan]::FromSeconds($s); '{0}h {1:00}m' -f [int][math]::Floor($t.TotalHours),$t.Minutes }
function Spark([int[]]$v,[int]$w=22){ if(-not $v -or $v.Count-eq0){return ''}
  $x=if($v.Count-gt$w){$v[($v.Count-$w)..($v.Count-1)]}else{$v}
  -join($x|ForEach-Object{ $i=[int][math]::Floor($_/12.6); if($i-lt0){$i=0}; if($i-gt7){$i=7}; $SPARK[$i] }) }
function TrialGrid([int]$done,[int]$tot){ $c=@(); for($k=1;$k-le$tot;$k++){ if($k-le$done){$c+=$CHK}else{$c+=$PEND} }; ($c -join '') }

$gpuHist=@{0=@();1=@();2=@();3=@()}; $frame=0
while($true){
  $frame++
  $raw = ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes -o ConnectTimeout=12 "root@$IP" "bash /root/mon_collect_a2d.sh" 2>$null
  if(-not $raw){ try{Clear-Host}catch{}; Write-Host "  (no response from $IP - retry in $RefreshSec s; frame $frame)" -ForegroundColor DarkYellow; if($Once){break}; Start-Sleep $RefreshSec; continue }
  # normalize to an array of lines regardless of how ssh returned it
  $lines = @($raw) | ForEach-Object { $_ -split "`n" } | ForEach-Object { $_.TrimEnd("`r") }
  $gpus=@{}; $bpmd=@(); $qm=@(); $kv=@{}
  foreach($ln in $lines){
    $ln=$ln.Trim(); if(-not $ln){continue}
    if($ln -match '^GPU=(\d+),(\d+),(\d+),(\d+)$'){ $gpus[[int]$Matches[1]]=@{util=[int]$Matches[2];mem=[int]$Matches[3];pw=[int]$Matches[4]}; continue }
    if($ln -match '^BPMD=(.+)$'){ $bpmd += ,($Matches[1] -split ','); continue }
    if($ln -match '^QM=(.+)$'){ $qm += ,($Matches[1] -split ','); continue }
    if($ln -match '^([A-Z]+)=(.*)$'){ $kv[$Matches[1]]=$Matches[2] }
  }
  foreach($gi in 0..3){ if($gpus.ContainsKey($gi)){ $gpuHist[$gi]+=$gpus[$gi].util; if($gpuHist[$gi].Count-gt160){$gpuHist[$gi]=$gpuHist[$gi][-160..-1]} } }

  try { Clear-Host } catch {}
  Write-Host ("="*78) -ForegroundColor DarkGray
  Write-Host ("  phenibut a2d - BPMD ladder + QM (Jaguar) on Scaleway H100x4 - LIVE   {0}  #{1}" -f (Get-Date -Format 'HH:mm:ss'),$frame) -ForegroundColor White
  Write-Host ("="*78) -ForegroundColor DarkGray

  # ---- GPUs ----
  $gpuActive=0
  foreach($gi in 0..3){
    if(-not $gpus.ContainsKey($gi)){continue}; $g=$gpus[$gi]
    if($g.util-gt10){$gpuActive++}
    $gcol=if($g.util-gt50){'Green'}elseif($g.util-gt0){'Yellow'}else{'DarkGray'}
    Write-Host ("  GPU{0} [{1}] {2,3}% {3,5}MiB {4,3}W  {5}" -f $gi,(Bar $g.util 14),$g.util,$g.mem,$g.pw,(Spark $gpuHist[$gi] 22)) -ForegroundColor $gcol
  }
  Write-Host ("  GPUs active: {0}/4" -f $gpuActive) -ForegroundColor $(if($gpuActive-ge3){'Green'}elseif($gpuActive-ge1){'Yellow'}else{'DarkGray'})
  Write-Host ("-"*78) -ForegroundColor DarkGray

  # ---- BPMD ladder (per-trial + MEASURED ETA) ----
  $bd=$kv['BPMDDONE']; if($bd){$bd=$bd -replace ',','/'}else{$bd='?/4'}
  Write-Host ("  BPMD LADDER   {0} done   (metadynamics ntrial=8, isolated-HOME pool; ETA measured from trial pace)" -f $bd) -ForegroundColor Cyan
  foreach($p in $bpmd){
    if($p.Count -lt 6){continue}
    $L=$p[0]; $g=$p[1]; $st=$p[2]; $el=[int]$p[3]; $tr=[int]$p[4]; $tot=[int]$p[5]
    $eta='--'
    if($st -eq 'done'){ $eta='complete' }
    elseif($st -eq 'failed'){ $eta='FAILED' }
    elseif($tr -ge 1 -and $el -gt 0){ $pace=$el/$tr; $eta='~'+(HMS ($pace*($tot-$tr)))+' left' }
    elseif($st -eq 'running'){ $eta='calibrating (trial 1)' }
    $scol=switch($st){'done'{'Green'}'running'{'Cyan'}'failed'{'Red'}'pending'{'DarkGray'}default{'Gray'}}
    Write-Host ("   [G{0}] {1,-11} {2,-8} {3} {4}/{5}  {6,8}  {7}" -f $g,$L,$st,(TrialGrid $tr $tot),$tr,$tot,(HMS $el),$eta) -ForegroundColor $scol
  }
  Write-Host ("-"*78) -ForegroundColor DarkGray

  # ---- QM (Jaguar interaction energies) ----
  $ieparts = ($kv['QMIE'] -split ','); $ieReady=$ieparts[0]; $ieTot=$ieparts[1]; $pk=$ieparts[2]
  $pkcol=switch($pk){'done'{'Green'}'running'{'Cyan'}default{'Red'}}
  Write-Host ("  QM CLUSTERS (B97-3c single-points; IE = cluster - ligand - pocket)") -ForegroundColor Cyan
  Write-Host ("   interaction energies ready: {0}/{1}   shared pocket: {2}" -f $ieReady,$ieTot,$pk) -ForegroundColor $(if($ieReady -eq $ieTot -and $ieTot){'Green'}elseif($pk -ne 'done'){'Yellow'}else{'Gray'})
  foreach($p in $qm){
    if($p.Count -lt 5){continue}
    $job=$p[0] -replace '_cluster',''; $st=$p[1]; $step=$p[2]; $en=$p[3]; $el=[int]$p[4]
    $isFail = ($st -like 'fail*')
    $scol=if($isFail){'Red'}elseif($st -eq 'done'){'Green'}elseif($st -eq 'running'){'Cyan'}else{'DarkGray'}
    $tag=if($isFail){"$X $st"}elseif($st -eq 'done'){"$CHK done"}else{$st}
    $sd=if($st -eq 'running' -and $step -ne '0'){"scf {0,3}" -f $step}elseif($st -eq 'running'){"integrals"}else{"        "}
    Write-Host ("   {0,-12} {1,-10} {2}  E={3,16}  {4}" -f $job,$tag,$sd,$en,(HMS $el)) -ForegroundColor $scol
  }
  Write-Host ("="*78) -ForegroundColor DarkGray
  Write-Host ("  Ctrl+C exit | box {0} | refresh {1}s | collector /root/mon_collect_a2d.sh" -f $IP,$RefreshSec) -ForegroundColor DarkGray

  if($Once){break}
  # terminal only when BOTH streams have no running work left (done or failed) — never false-positive
  $bpmdBusy = @($bpmd | Where-Object { $_[2] -eq 'running' -or $_[2] -eq 'pending' }).Count
  $qmBusy   = @($qm   | Where-Object { $_[1] -eq 'running' -or $_[1] -eq 'pending' }).Count
  if($bpmd.Count -gt 0 -and $qm.Count -gt 0 -and $bpmdBusy -eq 0 -and $qmBusy -eq 0){
    Write-Host "`n  All BPMD + QM jobs terminal (done/failed). Extract: proplister -c bpmd_<L>-out.maegz ; QM energies from /root/n1_qm/*_cluster.out" -ForegroundColor Green
    break
  }
  Start-Sleep $RefreshSec
}
