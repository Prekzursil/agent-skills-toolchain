# vm-link verify: full audit battery, home side. Terminal SUCCESS/FAILED per harness rules.
$fail = 0

# 1) home->VM SSH
$conf = Get-Content C:\ProgramData\vm-link\target.conf -First 1 -ErrorAction SilentlyContinue
$parts = if ($conf) { $conf -split '\s+' } else { @('prekzursil', 'offload-w2025') }
$vmUser, $vmHost = $parts[0], $parts[1]
Write-Host "target: $vmUser@$vmHost"
$sshOk = & ssh -i C:\ProgramData\vm-link\home_to_vm -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "$vmUser@$vmHost" hostname 2>$null
if ($sshOk) { Write-Host "  [OK] home->VM ssh ($sshOk)" } else { Write-Host '  [FAIL] home->VM ssh'; $fail++ }

# 2) VM serves reachable from home
foreach ($p in 2022, 2023) {
  $c = New-Object Net.Sockets.TcpClient
  try {
    [void]$c.ConnectAsync($vmHost, $p).Wait(5000)
    if ($c.Connected) { Write-Host "  [OK] VM serve :$p" } else { Write-Host "  [FAIL] VM serve :$p"; $fail++ }
  } catch { Write-Host "  [FAIL] VM serve :$p"; $fail++ } finally { $c.Close() }
}

# 3) tunnel task + home listeners
$task = (Get-ScheduledTask -TaskName 'home-link-tunnel' -ErrorAction SilentlyContinue).State
if ($task -eq 'Running') { Write-Host '  [OK] tunnel task Running' } else { Write-Host "  [FAIL] tunnel task = $task"; $fail++ }
$n = (Get-NetTCPConnection -LocalPort 2022, 2023, 21222, 21223 -State Listen -ErrorAction SilentlyContinue | Measure-Object).Count
if ($n -ge 4) { Write-Host "  [OK] home listeners ($n/4)" } else { Write-Host "  [FAIL] home listeners ($n/4)"; $fail++ }

# 4) serve tasks armed
$st = (Get-ScheduledTask -TaskName 'home-link-serve', 'home-link-serve-logon' -ErrorAction SilentlyContinue).State
if (@($st).Count -ge 2) { Write-Host '  [OK] serve tasks present' } else { Write-Host '  [FAIL] serve tasks missing'; $fail++ }

# 5) reaper safety
$wl = Select-String -Path "$env:USERPROFILE\.agents\scripts\reap_orphan_mcp.ps1" -Pattern 'vm-link' -SimpleMatch -Quiet
if ($wl) { Write-Host '  [OK] reaper whitelist has vm-link' } else { Write-Host '  [FAIL] reaper whitelist missing vm-link'; $fail++ }

if ($fail -eq 0) { Write-Host 'SUCCESS:vm-link-verify' } else { Write-Host "FAILED:vm-link-verify fail=$fail" }
exit $(if ($fail -eq 0) { 0 } else { 1 })
