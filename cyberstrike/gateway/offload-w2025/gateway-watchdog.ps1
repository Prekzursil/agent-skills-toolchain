# gateway-watchdog.ps1 - bounded external recovery for the live-assessment era.
# Contract deviation from "no watchdog" (estate G-rule for gateway DESIGN) is
# operator-approved 2026-10-01: the gateway is now a live dependency of the
# Bolt assessment sandbox and wedged twice in one hour.
# Logic: GET /mcp every 60s; 3 consecutive TIMEOUTs -> kill python gateway,
# schtasks /Run CyberStrikeGateway, log the event. ANY HTTP status = healthy.
$ErrorActionPreference = "Continue"
$Url = "http://127.0.0.1:31100/mcp"
$Log = "D:\opt\cyberstrike-mcp\logs\gateway-watchdog.log"
$fails = 0
while ($true) {
  $status = "ERR"
  try {
    $r = [System.Net.HttpWebRequest]::Create($Url)
    $r.Timeout = 10000
    $r.Method = "GET"
    $resp = $r.GetResponse()
    $status = [int]$resp.StatusCode
    $resp.Close()
  } catch [System.Net.WebException] {
    if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
    elseif ($_.Exception.Status -eq "Timeout") { $status = "TIMEOUT" }
  } catch { $status = "ERR" }
  if ($status -eq "TIMEOUT" -or $status -eq "ERR") {
    $fails++
    if ($fails -ge 3) {
      "$(Get-Date -Format s) WEDGE x$fails -> restarting gateway" | Add-Content $Log
      Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like "*gateway-server.py*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
      Start-Sleep -Seconds 3
      schtasks /Run /TN "CyberStrikeGateway" | Out-Null
      $fails = 0
    }
  } else { $fails = 0 }
  Start-Sleep -Seconds 60
}
