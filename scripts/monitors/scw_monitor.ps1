param(
  [string]$Title      = "monitor",
  [string]$Collector,                       # command string emitting protocol lines (run every refresh)
  [int]$RefreshSec    = 8,
  [switch]$Once
)
# ============================================================================
# scw_monitor.ps1 — GENERIC verbose terminal monitor (reusable template).
# Renders a small "monitor line protocol" emitted by ANY -Collector command, so
# one renderer covers GPU/HPC compute, Codex/agent workflows, CI, etc.
#
# PROTOCOL (collector prints one key=value per line, in display order):
#   HEAD=<section title>
#   GPU=<idx>,<util%>,<memMiB>,<watts>
#   JOB=<name>,<state>,<done>,<total>,<elapsedSec>,<detail>
#       state: done|running|failed|pending|<other>   (detail is free text; if empty and
#       done>0 a MEASURED ETA is shown from elapsed/done pace)
#   BAR=<label>,<pct>
#   KV=<label>,<value>[,<color>]
#   NOTE=<text>[,<color>]
#   DONE=<n>,<total>            (overall progress; terminal when n>=total AND no JOB running/pending)
# Unknown lines are ignored. -Once renders a single frame (for validation / hook probes).
#
# Examples:
#   scw_monitor.ps1 -Title "a2d" -Collector 'ssh box "bash /root/mon_collect_a2d.sh"'
#   scw_monitor.ps1 -Title "codex wave2" -Collector 'pwsh -File codex_collect.ps1 C:\...\wave2'
# ============================================================================
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$FULL=[char]0x2588; $EMPTY=[char]0x2591; $CHK=[char]0x2588; $PEND=[char]0x00B7; $XM=[char]0x2717
$SPARK=@(0x2581,0x2582,0x2583,0x2584,0x2585,0x2586,0x2587,0x2588)|ForEach-Object{[char]$_}

function Bar([double]$pct,[int]$w=18){ if($pct-lt0){$pct=0}; if($pct-gt100){$pct=100}
  $n=[int][math]::Round($w*$pct/100.0); ($FULL.ToString()*$n)+($EMPTY.ToString()*($w-$n)) }
function HMS([double]$s){ if($s-lt0){$s=0}; $t=[timespan]::FromSeconds($s); '{0}h {1:00}m' -f [int][math]::Floor($t.TotalHours),$t.Minutes }
function Spark([int[]]$v,[int]$w=22){ if(-not $v -or $v.Count-eq0){return ''}
  $x=if($v.Count-gt$w){$v[($v.Count-$w)..($v.Count-1)]}else{$v}
  -join($x|ForEach-Object{ $i=[int][math]::Floor($_/12.6); if($i-lt0){$i=0}; if($i-gt7){$i=7}; $SPARK[$i] }) }
function ProgGrid([int]$done,[int]$tot){ if($tot-le0){return ''}; if($tot-gt24){return (Bar (100.0*$done/$tot) 18)}
  $c=@(); for($k=1;$k-le$tot;$k++){ if($k-le$done){$c+=$CHK}else{$c+=$PEND} }; ($c -join '') }
function StateColor([string]$st){ switch -regex ($st){ 'done|ok|complete|success'{'Green'} 'run'{'Cyan'} 'fail|error|dead|scf_fail'{'Red'} 'pend|queue|wait'{'DarkGray'} default{'Gray'} } }

$gpuHist=@{}; $frame=0
while($true){
  $frame++
  $raw = try { Invoke-Expression $Collector 2>$null } catch { $null }
  if(-not $raw){ try{Clear-Host}catch{}; Write-Host ("  ($Title) no collector output - retry in ${RefreshSec}s (frame $frame)") -ForegroundColor DarkYellow; if($Once){break}; Start-Sleep $RefreshSec; continue }
  $lines = @($raw) | ForEach-Object { $_ -split "`n" } | ForEach-Object { $_.TrimEnd("`r").Trim() } | Where-Object { $_ }

  try { Clear-Host } catch {}
  Write-Host ("="*80) -ForegroundColor DarkGray
  Write-Host ("  {0}   {1}   (refresh {2}s  #{3})" -f $Title,(Get-Date -Format 'HH:mm:ss'),$RefreshSec,$frame) -ForegroundColor White
  Write-Host ("="*80) -ForegroundColor DarkGray

  $doneN=$null; $doneT=$null; $anyBusy=$false; $sawJob=$false
  foreach($ln in $lines){
    if($ln -notmatch '^([A-Z]+)=(.*)$'){ continue }
    $k=$Matches[1]; $v=$Matches[2]
    switch($k){
      'HEAD' { Write-Host ("-"*80) -ForegroundColor DarkGray; Write-Host ("  $v") -ForegroundColor Cyan }
      'GPU' {
        $p=$v -split ','; if($p.Count -lt 4){break}
        $i=[int]$p[0]; $u=[int]$p[1]; $m=$p[2]; $w=$p[3]
        if(-not $gpuHist.ContainsKey($i)){$gpuHist[$i]=@()}; $gpuHist[$i]+=$u; if($gpuHist[$i].Count-gt160){$gpuHist[$i]=$gpuHist[$i][-160..-1]}
        $gc=if($u-gt50){'Green'}elseif($u-gt0){'Yellow'}else{'DarkGray'}
        Write-Host ("  GPU{0} [{1}] {2,3}% {3,6}MiB {4,3}W  {5}" -f $i,(Bar $u 14),$u,$m,$w,(Spark $gpuHist[$i] 22)) -ForegroundColor $gc
      }
      'JOB' {
        $sawJob=$true; $p=$v -split ','; if($p.Count -lt 2){break}
        $name=$p[0]; $st=$p[1]
        $done=if($p.Count-ge3){[int]$p[2]}else{0}; $tot=if($p.Count-ge4){[int]$p[3]}else{0}
        $el=if($p.Count-ge5){[int]$p[4]}else{0}; $detail=if($p.Count-ge6){$p[5..($p.Count-1)] -join ','}else{''}
        if($st -match 'run|pend|queue|wait'){$anyBusy=$true}
        if(-not $detail){
          if($st -match 'fail|error|dead'){$detail='FAILED'}
          elseif($st -match 'done|complete|ok'){$detail='complete'}
          elseif($done -ge 1 -and $el -gt 0 -and $tot -gt 0){ $pace=$el/$done; $detail='~'+(HMS ($pace*($tot-$done)))+' left' }
        }
        $mk=if($st -match 'fail|error|dead'){"$XM"}elseif($st -match 'done|complete|ok'){"$CHK"}else{' '}
        $prog=if($tot-gt0){(ProgGrid $done $tot)+(" {0}/{1}" -f $done,$tot)}else{''}
        Write-Host ("  {0} {1,-16} {2,-9} {3}  {4,7}  {5}" -f $mk,$name,$st,$prog,(HMS $el),$detail) -ForegroundColor (StateColor $st)
      }
      'BAR' { $p=$v -split ','; if($p.Count-lt2){break}; $pct=[double]$p[1]
        Write-Host ("  {0,-20} [{1}] {2,3:0}%" -f $p[0],(Bar $pct 24),$pct) -ForegroundColor $(if($pct-ge100){'Green'}else{'White'}) }
      'KV'  { $p=$v -split ','; $col=if($p.Count-ge3 -and $p[2]){$p[2]}else{'Gray'}
        Write-Host ("  {0,-22} {1}" -f ($p[0]+':'),$p[1]) -ForegroundColor $col }
      'NOTE'{ $p=$v -split ','; $col=if($p.Count-ge2 -and $p[1]){$p[1]}else{'DarkGray'}
        Write-Host ("  {0}" -f $p[0]) -ForegroundColor $col }
      'DONE'{ $p=$v -split ','; if($p.Count-ge2){$doneN=[int]$p[0]; $doneT=[int]$p[1]} }
    }
  }
  Write-Host ("="*80) -ForegroundColor DarkGray
  $summ = if($doneT){"$doneN/$doneT done"}else{""}
  Write-Host ("  {0}  Ctrl+C exit | refresh {1}s | {2}" -f $summ,$RefreshSec,$Title) -ForegroundColor DarkGray

  if($Once){break}
  $terminal = ($doneT -ne $null -and $doneN -ge $doneT -and -not $anyBusy) -or ($sawJob -and -not $anyBusy -and $doneT -eq $null)
  if($terminal){ Write-Host "`n  All work terminal (done/failed)." -ForegroundColor Green; break }
  Start-Sleep $RefreshSec
}
