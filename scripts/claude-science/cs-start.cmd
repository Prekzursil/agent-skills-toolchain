@echo off
REM cs-start — start Claude Science if down (never kills a running one) and open its UI.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0cs-start.ps1" %*
