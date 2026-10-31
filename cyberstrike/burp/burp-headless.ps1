# burp-headless.ps1 — dialog-free Burp Pro + MCP launcher (v2, 2026-09-19)
# Replaces launch_burp_headless.ps1 (keygen-GUI + SendKeys + OCR chain).
#   - No startup dialog: --project-file pins the project (it carries the MCP BApp, SSE :9876)
#   - No keygen GUI: the -javaagent loader alone injects the existing license
#   - Window hidden at creation; survives with zero interaction
# Exit codes: 0 = MCP endpoint live; 1 = launch failed; 2 = endpoint never came up

$ErrorActionPreference = 'Continue'
$burpDir   = 'D:\opt\burp'
$jar       = Join-Path $burpDir 'burpsuite_pro_v2026.3.2.jar'
$project   = 'C:\Users\Prekzursil\Documents\2026-06-10.burp'
$jdk       = 'C:\Program Files\Microsoft\jdk-21.0.11.10-hotspot\bin\java.exe'
$mcpPort   = 9876
$logDir    = Join-Path $burpDir 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$log       = Join-Path $logDir 'launcher.log'

# First-line heartbeat: proves the script actually started (task-vs-script hangs
# are distinguishable instead of silent).
Write-Log '[.] launcher invoked'

function Write-Log($msg) {
    $line = "{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -Path $log -Value $line
    # rotate at ~2 MB, keep 3
    if ((Get-Item $log -ErrorAction SilentlyContinue).Length -gt 2MB) {
        for ($i = 2; $i -ge 1; $i--) {
            if (Test-Path "$log.$i") { Move-Item "$log.$i" "$log.$($i+1)" -Force }
        }
        Move-Item $log "$log.1" -Force
    }
}

function Test-McpPort {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $iar = $c.BeginConnect('127.0.0.1', $mcpPort, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne(1500)) { $c.Close(); return $false }
        $c.EndConnect($iar); $c.Close(); return $true
    } catch { return $false }
}

if (Test-McpPort) { Write-Log '[=] MCP already live on :9876 — nothing to do'; exit 0 }

# Kill only Burp JVMs (never SonarLint or other java processes)
Get-CimInstance Win32_Process -Filter "name='java.exe'" | Where-Object {
    $_.CommandLine -match 'burpsuite_pro'
} | ForEach-Object {
    Write-Log ("[x] killing stale Burp JVM pid=" + $_.ProcessId)
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 3

$args = @(
    '-Xmx2g',
    '-noverify',
    "-javaagent:$burpDir\BurpLoaderKeygen117.jar",
    '--add-opens=java.base/java.lang=ALL-UNNAMED',
    '--add-opens=java.desktop/javax.swing=ALL-UNNAMED',
    '--add-opens=java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED',
    '--add-opens=java.base/jdk.internal.org.objectweb.asm.tree=ALL-UNNAMED',
    '--add-opens=java.base/jdk.internal.org.objectweb.asm.Opcodes=ALL-UNNAMED',
    '-jar', $jar,
    "--project-file=$project",
    '--disable-auto-update',
    '--unpause-spider-and-scanner'
)

Write-Log '[*] launching Burp headless (hidden window, pinned project)'
$proc = Start-Process -FilePath $jdk -WorkingDirectory $burpDir -ArgumentList $args `
    -WindowStyle Hidden -PassThru
if (-not $proc) { Write-Log '[-] Start-Process failed'; exit 1 }
Write-Log "[+] JVM started pid=$($proc.Id); waiting for :$mcpPort (max 150s)"

$deadline = (Get-Date).AddSeconds(150)
while ((Get-Date) -lt $deadline) {
    if (Test-McpPort) {
        Write-Log "[+] SUCCESS: Burp MCP live on :$mcpPort (pid=$($proc.Id))"
        exit 0
    }
    if ($proc.HasExited) { Write-Log "[-] JVM died early (exit=$($proc.ExitCode))"; exit 1 }
    Start-Sleep -Seconds 5
}
Write-Log '[-] TIMEOUT: MCP endpoint never came up'
# WHY: exiting without cleanup leaves a half-booted JVM for the next launcher's kill-first pass to murder (restart loop) — reap only the JVM this script spawned, using the same burpsuite_pro guard as the kill-first block.
Get-CimInstance Win32_Process -Filter "name='java.exe'" | Where-Object {
    $_.ProcessId -eq $proc.Id -and $_.CommandLine -match 'burpsuite_pro'
} | ForEach-Object {
    Write-Log ("[x] timeout cleanup: killing spawned Burp JVM pid=" + $_.ProcessId)
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
exit 2
