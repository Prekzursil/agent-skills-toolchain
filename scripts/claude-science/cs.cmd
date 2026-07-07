@echo off
REM cs — cmd/PowerShell-5.1-safe entrypoint for the Claude Science dispatcher. Delegates to cs.ps1 next to it.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0cs.ps1" %*
