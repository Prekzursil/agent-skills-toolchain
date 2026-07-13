# a2d_translate.ps1 — emits the GENERIC monitor protocol from the a2d box collector,
# so the live BPMD+QM compute renders through the generic scw_monitor.ps1 template.
#   scw_monitor.ps1 -Title "phenibut a2d" -Collector 'pwsh -NoProfile -File <this>'
$raw = ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes -o ConnectTimeout=12 root@51.159.182.130 "bash /root/mon_collect_a2d.sh" 2>$null
$lines = @($raw) | ForEach-Object { $_ -split "`n" } | ForEach-Object { $_.TrimEnd("`r").Trim() } | Where-Object { $_ }

Write-Output "HEAD=GPUs (Scaleway H100 x4)"
foreach($l in $lines){ if($l -match '^GPU=(.+)$'){ Write-Output ("GPU=" + $Matches[1]) } }

Write-Output "HEAD=BPMD ladder (metadynamics, ntrial=8, isolated-HOME pool)"
$bpmdDone='0'; $bpmdTot='4'
foreach($l in $lines){
  if($l -match '^BPMD=([^,]+),(\d+),([^,]+),(\d+),(\d+),(\d+)$'){
    Write-Output ("JOB=[G{0}] {1},{2},{3},{4},{5}," -f $Matches[2],$Matches[1],$Matches[3],$Matches[5],$Matches[6],$Matches[4])
  }
  if($l -match '^BPMDDONE=(\d+),(\d+)$'){ $bpmdDone=$Matches[1]; $bpmdTot=$Matches[2] }
}

Write-Output "HEAD=QM clusters (Jaguar B97-3c; IE = cluster - ligand - pocket)"
foreach($l in $lines){
  if($l -match '^QM=([^,]+),([^,]+),([^,]+),([^,]+),(\d+)$'){
    $j=$Matches[1] -replace '_cluster',''; $st=$Matches[2]; $step=$Matches[3]; $en=$Matches[4]; $el=$Matches[5]
    $det = if($st -like 'fail*'){"SCF fail (ERROR 2256)"} elseif($st -eq 'running' -and $step -ne '0'){"scf $step  E=$en"} elseif($st -eq 'running'){"integrals"} else {""}
    Write-Output ("JOB={0},{1},0,0,{2},{3}" -f $j,$st,$el,$det)
  }
}
foreach($l in $lines){
  if($l -match '^QMIE=(\d+),(\d+),(.+)$'){ Write-Output ("KV=interaction energies,{0}/{1} (shared pocket: {2})" -f $Matches[1],$Matches[2],$Matches[3]) }
}
Write-Output ("DONE={0},{1}" -f $bpmdDone,$bpmdTot)
