$ErrorActionPreference = 'SilentlyContinue'
$all = Get-CimInstance Win32_Process
$byPid = @{}
foreach ($p in $all) { $byPid[[uint32]$p.ProcessId] = $p }

function ParentName($p) {
  $pp = $byPid[[uint32]$p.ParentProcessId]
  if ($pp) { "$($pp.Name)($($pp.ParentProcessId))" } else { "DEAD($($p.ParentProcessId))" }
}

"=== Target trees grouped by parent ==="
$targets = $all | Where-Object { $_.Name -in ('pwsh.exe','powershell.exe','node.exe','python.exe','pythonw.exe','comet.exe') }
$targets | Group-Object { "$($_.Name) <- parent $(ParentName $_)" } | Sort-Object Count -Descending | ForEach-Object {
  "{0,3}x  {1}" -f $_.Count, $_.Name
}

""
"=== Top 18 by PRIVATE memory (all processes) ==="
Get-Process | Sort-Object PrivateMemorySize64 -Descending | Select-Object -First 18 Name, Id,
  @{n='Priv_MB';e={[math]::Round($_.PrivateMemorySize64/1MB)}},
  @{n='WS_MB';e={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table -AutoSize

""
"=== Commit / pools ==="
$m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
"CommitPct:      $($m.PercentCommittedInUse)%"
"Committed_GB:   $([math]::Round($m.CommittedBytes/1GB,1))"
"CommitLimit_GB: $([math]::Round($m.CommitLimit/1GB,1))"
"PoolNonpaged_MB: $([math]::Round($m.PoolNonpagedBytes/1MB))"
"PoolPaged_MB:    $([math]::Round($m.PoolPagedBytes/1MB))"

""
"=== comet + node + remaining pwsh detail (cmd truncated) ==="
foreach ($p in ($targets | Where-Object { $_.Name -in ('comet.exe','node.exe') })) {
  $cmd = if ($p.CommandLine) { $p.CommandLine.Substring(0,[Math]::Min(100,$p.CommandLine.Length)) } else { '' }
  "{0,-10} pid={1,-7} parent={2,-22} start={3}  {4}" -f $p.Name, $p.ProcessId, (ParentName $p), $p.CreationDate.ToString('HH:mm'), $cmd
}
