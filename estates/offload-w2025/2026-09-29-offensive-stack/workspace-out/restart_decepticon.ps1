$ErrorActionPreference = 'Continue'
# kill every decepticon MCP server / streamlit process, then start once via the staged script
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
    $_.CommandLine -match 'decepticon' -or
    $_.CommandLine -match 'Reconnaissance\.py' -or
    $_.CommandLine -match 'Initial_Access\.py' -or
    $_.CommandLine -match 'src.tools.mcp.terminal\.py' -or
    $_.CommandLine -match 'streamlit_app\.py'
}
foreach ($p in $procs) {
    Write-Output ('stopping ' + $p.ProcessId + ': ' + $p.CommandLine.Substring(0, [Math]::Min(80, $p.CommandLine.Length)))
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 3
& 'D:\opt\decepticon\start-decepticon.ps1' -NoUi
Start-Sleep -Seconds 18
Write-Output '--- listeners ---'
Get-NetTCPConnection -State Listen -LocalPort 3001,3002,3003,8501 -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Output ($_.LocalAddress + ':' + $_.LocalPort + ' pid ' + $_.OwningProcess) }
