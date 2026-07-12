@echo off
rem wfmon — thin front-end over the generalized `mon` launcher.
rem   wfmon board            = plain-text board (workflow_run.py)
rem   wfmon export <id> ...  = redacted timeline export CLI (python -m wfmon_export)
rem   wfmon [args]           = the whole-fleet cockpit — delegated to `mon wfmon` when the
rem                            generalized launcher is on PATH (opens a reusable 'wfmon'
rem                            Windows-Terminal window); otherwise the direct foreground launch.
set "SK=%USERPROFILE%\.agents\skills\workflow-monitor"
if /I "%~1"=="board" (
  python "%SK%\workflow_run.py"
  goto :eof
)
if /I "%~1"=="export" (
  pushd "%SK%" & python -m wfmon_export %* & popd
  goto :eof
)
where mon >nul 2>nul && ( call mon wfmon %* ) || ( python "%SK%\workflow_monitor.py" %* )
