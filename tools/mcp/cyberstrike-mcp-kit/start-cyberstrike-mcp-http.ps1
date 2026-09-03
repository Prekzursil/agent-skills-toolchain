#Requires -Version 5.1
<#
.SYNOPSIS
  Keep CyberStrike stdio MCPs behind loopback Streamable HTTP (G-7 pattern).
.DESCRIPTION
  One supervisor. Spawns mcp-proxy --host 127.0.0.1 --no-eventStore per server.
  Does not print secrets. Bind is loopback only (mcp-proxy default host is ::).
#>
$ErrorActionPreference = 'Continue'
# Search-hub / Tavily / Exa / onions stay on Grok. Do not front them here.
function Import-UserEnv([string]$name) {
  try {
    $v = [Environment]::GetEnvironmentVariable($name, 'User')
    if ($v) { Set-Item -Path ("Env:{0}" -f $name) -Value $v }
  } catch {}
}
foreach ($n in @('GITHUB_TOKEN','NVD_API_KEY','FIRECRAWL_API_KEY','FIRECRAWL_API_URL','SHODAN_API_KEY','VT_API_KEY','ST_API_KEY','CENSYS_API_ID','CENSYS_API_SECRET','MSF_API_USER','MSF_API_PASSWORD')) {
  Import-UserEnv $n
}
$Proxy = 'D:\opt\cyberstrike-mcp\node_modules\mcp-proxy\dist\bin\mcp-proxy.mjs'
$Node = 'C:\Program Files\nodejs\node.exe'
$Cmd = 'C:\Windows\System32\cmd.exe'
$Py = 'C:\Python314\python.exe'

$fronts = @(
  @{ Name = 'github-security'; Port = 31410; Exe = $Cmd; Args = @('/d','/c','D:\opt\cyberstrike-mcp\github-security-mcp.cmd') }
  @{ Name = 'cve';             Port = 31411; Exe = $Cmd; Args = @('/d','/c','D:\opt\cyberstrike-mcp\cve-mcp.cmd') }
  @{ Name = 'osint';           Port = 31412; Exe = $Cmd; Args = @('/d','/c','D:\opt\cyberstrike-mcp\osint-mcp-server.cmd') }
  @{ Name = 'hexstrike-ai';    Port = 31413; Exe = 'C:\Users\Prekzursil\.local\opt\hexstrike-ai\.venv\Scripts\python.exe'; Args = @('C:\Users\Prekzursil\.local\opt\hexstrike-ai\hexstrike_mcp_launcher.py') }
  @{ Name = 'firecrawl';       Port = 31414; Exe = $Py; Args = @('D:\opt\cyberstrike-mcp\firecrawl-mcp-launch.py') }
  @{ Name = 'hacktricks';      Port = 31415; Exe = $Py; Args = @('D:\opt\cyberstrike-mcp\hacktricks-mcp-launch.py') }
  @{ Name = 'metasploit';      Port = 31416; Exe = $Py; Args = @('D:\opt\metasploit\msfmcpd-stdio.py') }
  @{ Name = 'nuclei';          Port = 31417; Exe = $Cmd; Args = @('/d','/c','D:\opt\cyberstrike-mcp\nuclei-mcp.cmd') }
  @{ Name = 'cloud-audit';     Port = 31418; Exe = $Cmd; Args = @('/d','/c','D:\opt\cyberstrike-mcp\cloud-audit-mcp.cmd') }
  @{ Name = 'semgrep';         Port = 31419; Exe = $Cmd; Args = @('/d','/c','D:\opt\cyberstrike-mcp\semgrep-mcp.cmd') }
  @{ Name = 'sliver';          Port = 31380; Exe = $Cmd; Args = @('/d','/c','D:\opt\cyberstrike-mcp\sliver-client-mcp-http.cmd'); Match = '--port 31380'; Raw = $true }
  @{ Name = 'sliver-full';     Port = 31381; Exe = $Cmd; Args = @('/d','/c','D:\opt\cyberstrike-mcp\sliver-full-mcp-http.cmd'); Match = 'sliver-full-http.py'; Raw = $true }
)

function Test-Port([int]$Port) {
  try {
    $t = New-Object System.Net.Sockets.TcpClient
    $iar = $t.BeginConnect('127.0.0.1', $Port, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne(200, $false) -and $t.Connected
    $t.Close()
    return $ok
  } catch { return $false }
}

function Get-HungProc([string]$MatchText) {
  if (-not $MatchText) { return @() }
  try {
    return @(Get-CimInstance Win32_Process -Filter "Name='node.exe' or Name='python.exe'" |
      Where-Object { $_.CommandLine -and $_.CommandLine.Contains($MatchText) })
  } catch { return @() }
}

function Start-Front($f) {
  if (Test-Port $f.Port) { Write-Host ("HAVE {0} :{1}" -f $f.Name, $f.Port); return }
  # Zombie reap: a hung child that never bound its port would otherwise
  # accumulate across heal cycles (sliver connect() has no timeout).
  $hung = Get-HungProc $f.Match
  foreach ($p in $hung) {
    try {
      Write-Host ("REAP {0} hung pid={1}" -f $f.Name, $p.ProcessId)
      Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    } catch {}
  }
  if ($hung.Count -gt 0) { Start-Sleep -Seconds 2 }
  if ($f.Raw) {
    # Raw fronts manage their own transport (shim runs mcp-proxy or a direct
    # HTTP server on the target port). Spawning through another mcp-proxy
    # would double-proxy and race the port bind.
    $p = Start-Process -FilePath $f.Exe -ArgumentList $f.Args -WorkingDirectory 'D:\opt\cyberstrike-mcp' -WindowStyle Hidden -PassThru
    Write-Host ("START-RAW {0} :{1} pid={2}" -f $f.Name, $f.Port, $p.Id)
    return
  }
  $proxyArgs = @(
    $Proxy,
    '--host','127.0.0.1',
    '--port', [string]$f.Port,
    '--server','stream',
    '--no-eventStore',
    '--',
    $f.Exe
  ) + $f.Args
  $p = Start-Process -FilePath $Node -ArgumentList $proxyArgs -WorkingDirectory 'D:\opt\cyberstrike-mcp' -WindowStyle Hidden -PassThru
  Write-Host ("START {0} :{1} pid={2}" -f $f.Name, $f.Port, $p.Id)
}

foreach ($f in $fronts) { Start-Front $f }

# Keep the scheduled task alive; children are independent Start-Process.
while ($true) {
  Start-Sleep -Seconds 30
  foreach ($f in $fronts) {
    if (-not (Test-Port $f.Port)) { Start-Front $f }
  }
}
