@echo off
REM cs-recover -- recover/restart Claude Science and reopen its UI.
REM
REM PREFER PowerShell 7, FALL BACK to Windows PowerShell 5.1. Measured 2026-08-12: these shims
REM named `powershell` (5.1) unconditionally, so `cs doctor` from cmd.exe and `/claude-science`
REM (which runs `pwsh -File cs.ps1`) produced DIFFERENT reports on the same box in the same
REM minute -- 5.1: "0 FAIL, 2 WARN, 4 NOT-CHECKED, 8 PASS" against pwsh: "0 FAIL, 1 WARN,
REM 0 NOT-CHECKED, 13 PASS". Root cause: Windows PowerShell 5.1 mangles native-command arguments
REM containing embedded double quotes, and the DB/backup probes hand wsl.exe a quoted
REM `sqlite3 -readonly "file:...?mode=ro"`, so under 5.1 bash receives a truncated command
REM ("-readonly: -c: line 2: unexpected EOF") and those rows render NOT-CHECKED.
REM Rows going NOT-CHECKED is the fail-closed contract working -- an unmeasurable probe must never
REM read PASS -- but two routes disagreeing about the same box is the D1 defect class, so the shim
REM now picks the host that can actually run the probes. The 5.1 path is kept as a fallback.
REM
REM Written WITHOUT `where /q pwsh && (A) || (B)`: in cmd that also runs B whenever A exits
REM non-zero, and `cs doctor` exits non-zero BY DESIGN on any FAIL or NOT-CHECKED.
setlocal
set "CS_PS=powershell"
where /q pwsh && set "CS_PS=pwsh"
"%CS_PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0cs-recover.ps1" %*
exit /b %ERRORLEVEL%
