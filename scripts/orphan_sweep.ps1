# Orphan sweep: kill target-named processes whose parent no longer exists.
# Protects: current process ancestor chain, anything with a live parent.
$ErrorActionPreference = 'SilentlyContinue'

$targetNames = @('pwsh.exe','powershell.exe','node.exe','python.exe','pythonw.exe','comet.exe')

function FreeGB { $o=Get-CimInstance Win32_OperatingSystem; [math]::Round($o.FreePhysicalMemory/1MB,1) }

$all = Get-CimInstance Win32_Process
$live = @{}
foreach ($p in $all) { $live[[uint32]$p.ProcessId] = $true }

# Build protected set = ancestors of current PID
$byPid = @{}
foreach ($p in $all) { $byPid[[uint32]$p.ProcessId] = $p }
$protected = @{}
$cur = [uint32]$PID
while ($cur -and $byPid.ContainsKey($cur)) {
  $protected[$cur] = $true
  $cur = [uint32]$byPid[$cur].ParentProcessId
  if ($protected.ContainsKey($cur)) { break }  # loop guard
}

"Free before: $(FreeGB) GB"
"Protected chain: $($protected.Keys -join ',')"

$cutoff = (Get-Date).AddMinutes(-10)
$victims = @()
foreach ($p in $all) {
  if ($targetNames -notcontains $p.Name) { continue }
  if ($protected.ContainsKey([uint32]$p.ProcessId)) { continue }
  $ppid = [uint32]$p.ParentProcessId
  if ($ppid -eq 0 -or $live.ContainsKey($ppid)) { continue }   # parent alive -> skip
  if ($p.CreationDate -and $p.CreationDate -gt $cutoff) { continue }  # too young, give grace
  $victims += $p
}

"--- Orphan victims ($($victims.Count)) ---"
foreach ($v in $victims) {
  $ws = 0
  $gp = Get-Process -Id $v.ProcessId
  if ($gp) { $ws = [math]::Round($gp.WorkingSet64/1MB) }
  $age = if ($v.CreationDate) { [math]::Round(((Get-Date) - $v.CreationDate).TotalMinutes) } else { '?' }
  $cmd = if ($v.CommandLine) { $v.CommandLine.Substring(0,[Math]::Min(110,$v.CommandLine.Length)) } else { '' }
  "{0,-16} pid={1,-7} ppid={2,-7} ageMin={3,-6} WS={4}MB  {5}" -f $v.Name, $v.ProcessId, $v.ParentProcessId, $age, $ws, $cmd
}

$totalFreed = 0
foreach ($v in $victims) {
  $gp = Get-Process -Id $v.ProcessId -ErrorAction SilentlyContinue
  if ($gp) { $totalFreed += $gp.WorkingSet64 }
  Stop-Process -Id $v.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 3
""
"Killed $($victims.Count) orphans (working-set total ~$([math]::Round($totalFreed/1MB)) MB)"
"Free after: $(FreeGB) GB"

# Still-running duplicates report
""
"=== Remaining target-name processes ==="
Get-Process | Where-Object { $_.Name -in ('pwsh','powershell','node','python','comet') } |
  Group-Object Name | ForEach-Object { "{0,-12} count={1}" -f $_.Name, $_.Count }
