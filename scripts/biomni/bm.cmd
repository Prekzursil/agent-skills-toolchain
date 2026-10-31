@echo off
rem bm - shim so `bm` works from any shell (PowerShell 5.1-compatible invocation).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bm.ps1" %*
