$ErrorActionPreference = 'SilentlyContinue'
$os = Get-CimInstance Win32_OperatingSystem
$m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
"FreeRAM_GB:   $([math]::Round($os.FreePhysicalMemory/1MB,1))"
"PagedPool_GB: $([math]::Round($m.PoolPagedBytes/1GB,1))"
"NonPaged_GB:  $([math]::Round($m.PoolNonpagedBytes/1GB,1))"
"Committed_GB: $([math]::Round($m.CommittedBytes/1GB,1))"
""
"cyberstrike.exe instances:"
Get-Process cyberstrike | ForEach-Object { "  pid=$($_.Id) WS_MB=$([math]::Round($_.WorkingSet64/1MB)) Priv_MB=$([math]::Round($_.PrivateMemorySize64/1MB))" }
""
"Remaining dup counts (pwsh/node/python):"
(Get-Process pwsh -ErrorAction SilentlyContinue).Count; (Get-Process node -ErrorAction SilentlyContinue).Count; (Get-Process python -ErrorAction SilentlyContinue).Count
""
"Disk-verify command file + patched server:"
Get-Item "C:\Users\Prekzursil\.config\cyberstrike\command\jailbreak.md" | ForEach-Object { "  jailbreak.md OK $($_.Length) bytes" }
Get-Item "D:\opt\cyberstrike-mcp\jb-library-mcp-server.py" | ForEach-Object { "  jb-library-server OK $($_.Length) bytes (modified $($_.LastWriteTime.ToString('HH:mm:ss')))" }
Select-String -Path "D:\opt\cyberstrike-mcp\jb-library-mcp-server.py" -Pattern "_sanitize" -SimpleMatch | Measure-Object | ForEach-Object { "  sanitize refs in server: $($_.Count)" }
"py syntax check:"
& C:\Python314\python.exe -m py_compile "D:\opt\cyberstrike-mcp\jb-library-mcp-server.py"
if ($LASTEXITCODE -eq 0) { "  COMPILE OK" } else { "  COMPILE FAILED" }
