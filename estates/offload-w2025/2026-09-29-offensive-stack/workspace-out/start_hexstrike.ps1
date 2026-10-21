$root = 'D:\opt\hexstrike-ai'
$logs = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$env:HEXSTRIKE_HOST = '127.0.0.1'
$env:HEXSTRIKE_PORT = '18888'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Start-Process -FilePath (Join-Path $root '.venv\Scripts\python.exe') `
    -ArgumentList ('"' + (Join-Path $root 'repo\hexstrike_server.py') + '"') `
    -WorkingDirectory (Join-Path $root 'repo') -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logs 'server.stdout.log') `
    -RedirectStandardError (Join-Path $logs 'server.stderr.log')
Write-Output 'spawned hexstrike on 127.0.0.1:18888 (detached)'
