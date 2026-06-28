@echo off
REM ===========================================================================
REM  Claude Code Agent Monitor  -  double-click launcher (opens the UI)
REM  Just double-click this file, or run it with no arguments.
REM  Power users: agent_monitor.py --watch / --spawn  (legacy terminal modes)
REM ===========================================================================
setlocal
cd /d "%~dp0"

REM --- resolve a WINDOWED python (pythonw = no console), then fall back ---
set "PYW="
where pythonw >nul 2>&1 && set "PYW=pythonw"
if not defined PYW ( where py >nul 2>&1 && set "PYW=py -3" )
if not defined PYW ( where python >nul 2>&1 && set "PYW=python" )
if not defined PYW (
  echo [ERROR] Python 3 not found on PATH. Install from https://python.org and re-run.
  pause & exit /b 1
)

start "" %PYW% "%~dp0agent_monitor_ui.py"
endlocal
