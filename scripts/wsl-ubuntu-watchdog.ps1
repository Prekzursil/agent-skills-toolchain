# wsl-ubuntu-watchdog.ps1 - self-healing guard for the wedged-Ubuntu failure class
# Created 2026-09-29 after the all-night Wsl/Service/0x8007274c wedge incident.
# Doctrine: probes Ubuntu exec with a hard timeout; if wedged, terminates ONLY Ubuntu.
# NEVER touches docker-desktop or any other distro. Logs one line per action.
# Failure philosophy: fail-open (a watchdog error must never make things worse).

$ErrorActionPreference = 'SilentlyContinue'
$log = 'C:\Users\Prekzursil\.agents\logs\wsl-ubuntu-watchdog.log'
New-Item -ItemType Directory -Path (Split-Path $log) -Force | Out-Null

function Write-Log([string]$msg) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg" | Add-Content -Path $log -Encoding utf8
    # ring: keep last 400 lines
    $c = Get-Content $log -ErrorAction SilentlyContinue
    if ($c.Count -gt 400) { $c | Select-Object -Last 400 | Set-Content $log -Encoding utf8 }
}

function Get-UbuntuState {
    # wsl.exe emits UTF-16LE with embedded NUL chars - strip them or the regex never matches
    $raw = & wsl.exe -l -v 2>&1
    $out = ($raw | Out-String).Replace([string][char]0, '')
    foreach ($line in ($out -split "`n")) {
        if ($line -match '^\s*\*?\s*Ubuntu\s+(\S+)') { return $Matches[1] }
    }
    return 'Unknown'
}

# 1. Stopped/absent = healthy, nothing to do (silent - this is the common case)
$state = Get-UbuntuState
if ($state -ne 'Running') { exit 0 }

# 2. Running: probe the session layer with a hard 20s bound
$probe = Start-Process -FilePath 'wsl.exe' -ArgumentList '-d','Ubuntu','-u','root','-e','echo','probe-ok' `
    -WindowStyle Hidden -PassThru -RedirectStandardOutput "$env:TEMP\wslwd-out.txt" -RedirectStandardError "$env:TEMP\wslwd-err.txt"
if (-not $probe.WaitForExit(20000)) {
    # 3. Wedged: kill the probe, terminate ONLY Ubuntu, log
    if (-not $probe.HasExited) { try { $probe.Kill() } catch {} }
    wsl.exe --terminate Ubuntu 2>&1 | Out-Null
    Start-Sleep -Seconds 3
    $after = Get-UbuntuState
    Write-Log "WEDGE-DETECTED state=Running probe=TIMEOUT(20s) -> terminated Ubuntu; after=$after"
    exit 0
}

if ($probe.ExitCode -eq 0) {
    exit 0   # healthy - silent
}
else {
    # answered but with error: one soft retry before terminating (avoid flapping on transient)
    Start-Sleep -Seconds 5
    $probe2 = Start-Process -FilePath 'wsl.exe' -ArgumentList '-d','Ubuntu','-u','root','-e','echo','probe-ok' `
        -WindowStyle Hidden -PassThru -RedirectStandardOutput "$env:TEMP\wslwd-out2.txt" -RedirectStandardError "$env:TEMP\wslwd-err2.txt"
    if (-not $probe2.WaitForExit(20000)) {
        if (-not $probe2.HasExited) { try { $probe2.Kill() } catch {} }
        wsl.exe --terminate Ubuntu 2>&1 | Out-Null
        Start-Sleep -Seconds 3
        Write-Log "WEDGE-DETECTED probe=exit($($probe.ExitCode)) retry=TIMEOUT -> terminated Ubuntu"
    } else {
        Write-Log "TRANSIENT probe=exit($($probe.ExitCode)) retry=exit($($probe2.ExitCode)) -> left running"
    }
}
exit 0
