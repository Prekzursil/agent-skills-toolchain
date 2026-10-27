$p = Get-Process -Id 177813 -ErrorAction SilentlyContinue
if ($p) { Write-Output ("verify.py 177813 alive, CPU=" + $p.CPU) } else { Write-Output "verify.py 177813 GONE" }
Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq 177813 } | ForEach-Object {
  $cl = $_.CommandLine
  if ($cl -and $cl.Length -gt 150) { $cl = $cl.Substring(0,150) }
  Write-Output ("child " + $_.ProcessId + " " + $_.Name + " :: " + $cl)
}
Write-Output "---all python children one level under bash from verify---"
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'AUD-00' } | ForEach-Object {
  $cl = $_.CommandLine
  if ($cl -and $cl.Length -gt 150) { $cl = $cl.Substring(0,150) }
  Write-Output ("AUD-probe " + $_.ProcessId + " :: " + $cl)
}
