@echo off
REM cs-recover — recover/restart Claude Science and reopen its UI. Delegates to the PS1 next to it.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0cs-recover.ps1" %*
