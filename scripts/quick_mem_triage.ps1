$os = Get-CimInstance Win32_OperatingSystem
"FREE_GB: " + [math]::Round($os.FreePhysicalMemory/1MB,1)
"TOTAL_GB: " + [math]::Round($os.TotalVisibleMemorySize/1MB,1)
""
"=== Top process groups by total working set ==="
Get-Process | Group-Object Name | ForEach-Object {
  [PSCustomObject]@{
    Name = $_.Name
    Count = $_.Count
    TotalWS_MB = [math]::Round(($_.Group | Measure-Object WorkingSet64 -Sum).Sum/1MB)
  }
} | Sort-Object TotalWS_MB -Descending | Select-Object -First 25 | Format-Table -AutoSize
