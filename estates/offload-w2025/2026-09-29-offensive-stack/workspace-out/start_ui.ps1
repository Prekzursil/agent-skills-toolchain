$root = 'D:\opt\decepticon'
$py = Join-Path $root '.venv\Scripts\python.exe'
$logs = 'D:\tmp'
Start-Process -FilePath $py `
    -ArgumentList @('-m', 'streamlit', 'run', 'frontend\streamlit_app.py', `
        '--server.headless', 'true', '--server.address', '127.0.0.1', '--server.port', '8501', '--browser.gatherUsageStats', 'false') `
    -WorkingDirectory $root -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logs 'dc-streamlit.out.log') `
    -RedirectStandardError (Join-Path $logs 'dc-streamlit.err.log')
Write-Output 'streamlit starting on 127.0.0.1:8501'
