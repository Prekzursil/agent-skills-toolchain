$ErrorActionPreference = 'SilentlyContinue'
# Mechanically different probe from mcp_doctor.py: direct WMI Win32_Process command-line scan
$node = Get-CimInstance Win32_Process -Filter "Name='node.exe'" -Property ProcessId,CommandLine
"TOTAL_NODE=$(@($node).Count)"
$pw = @($node | Where-Object { $_.CommandLine -match 'playwright' })
"NODE_PLAYWRIGHT_COUNT=$($pw.Count)"
$pw | ForEach-Object {
  $c = ($_.CommandLine -replace '\s+',' ')
  if ($c.Length -gt 150) { $c = $c.Substring(0,150) }
  "PW_PID=$($_.ProcessId) CMD=$c"
}
$hub = @($node | Where-Object { $_.CommandLine -match 'meta-tool|hub' })
"NODE_HUBLIKE_COUNT=$($hub.Count)"
$hub | Select-Object -First 5 | ForEach-Object {
  $c = ($_.CommandLine -replace '\s+',' ')
  if ($c.Length -gt 150) { $c = $c.Substring(0,150) }
  "HUB_PID=$($_.ProcessId) CMD=$c"
}
$py = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -Property ProcessId,CommandLine
"TOTAL_PY=$(@($py).Count)"
@($py) | Where-Object { $_.CommandLine -match 'playwright|pubmed|pdf.reader|postgres' } | Select-Object -First 15 | ForEach-Object {
  $c = ($_.CommandLine -replace '\s+',' ')
  if ($c.Length -gt 150) { $c = $c.Substring(0,150) }
  "PY_PID=$($_.ProcessId) CMD=$c"
}
$dk = Get-CimInstance Win32_Process -Filter "Name='docker.exe'" -Property ProcessId,CommandLine
"DOCKER_CLI_PROCS=$(@($dk).Count)"
@($dk) | Select-Object -First 5 | ForEach-Object {
  $c = ($_.CommandLine -replace '\s+',' ')
  if ($c.Length -gt 120) { $c = $c.Substring(0,120) }
  "DOCKER_PID=$($_.ProcessId) CMD=$c"
}
$dd = Get-CimInstance Win32_Process -Filter "Name='com.docker.backend' OR Name='Docker Desktop'" -Property Name
"DOCKER_DAEMON_PROCS=$(@($dd).Count)"
"PROBE_DONE"
