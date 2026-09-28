@echo off
setlocal
rem claude-free - a DEDICATED Claude Code instance on the free GLM lane.
rem Starts the shim if down, then launches claude pointed at it.
rem Never use this env inside an existing session - separate instance only.
rem CLAUDE_CONFIG_DIR keeps the full AGENTS.md import. Official claude does not.
tasklist /FI "IMAGENAME eq python.exe" 2>nul | findstr /i python >nul || echo starting
powershell -NoProfile -Command "if (-not (Get-NetTCPConnection -LocalPort 18400 -State Listen -ErrorAction SilentlyContinue)) { Start-Process -WindowStyle Hidden -FilePath python -ArgumentList 'C:\Users\Prekzursil\.local\bin\glm-free-shim.py' -RedirectStandardOutput 'D:\Research\tools\biomni-local\glm-shim.log' -RedirectStandardError 'D:\Research\tools\biomni-local\glm-shim.err.log' }"
set CLAUDE_CONFIG_DIR=C:\Users\Prekzursil\.claude-free
set ANTHROPIC_BASE_URL=http://127.0.0.1:18400
set ANTHROPIC_AUTH_TOKEN=free-lane-local
set ANTHROPIC_MODEL=glm-free
set ANTHROPIC_SMALL_FAST_MODEL=glm-free
claude %*
