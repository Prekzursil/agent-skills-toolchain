$ErrorActionPreference = 'SilentlyContinue'
$root = 'D:\opt\cyberstrike-mcp'
$proxy = Join-Path $root 'node_modules\mcp-proxy\dist\bin\mcp-proxy.mjs'
$node = 'C:\Program Files\nodejs\node.exe'

$tests = @(
  @{ name='github-security'; exe='C:\Windows\System32\cmd.exe';
     args=@('/d','/c',(Join-Path $root 'github-security-mcp.cmd')); port=31410 },
  @{ name='hacktricks'; exe='C:\Python314\python.exe';
     args=@((Join-Path $root 'hacktricks-mcp-launch.py')); port=31415 }
)

foreach ($t in $tests) {
  $err = "$env:TEMP\front_$($t.name).err"
  $out = "$env:TEMP\front_$($t.name).out"
  Remove-Item $err,$out -Force
  $full = @($proxy,'--host','127.0.0.1','--port',[string]$t.port,'--server','stream','--no-eventStore','--',$t.exe) + $t.args
  "=== $($t.name) :$($t.port) ==="
  $p = Start-Process -FilePath $node -ArgumentList $full -WorkingDirectory $root -WindowStyle Hidden -PassThru `
       -RedirectStandardError $err -RedirectStandardOutput $out
  Start-Sleep -Seconds 8
  if ($p.HasExited) { "proxy EXITED code=$($p.ExitCode)" } else { "proxy alive pid=$($p.Id)"; Stop-Process -Id $p.Id -Force }
  "--- stderr ---"
  Get-Content $err -TotalCount 12
  "--- stdout ---"
  Get-Content $out -TotalCount 6
  ""
}
