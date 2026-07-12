@echo off
rem wfmon — launch the whole-fleet workflow-monitor cockpit.  `wfmon board` = plain-text board.
rem `wfmon export <wf_id> [opts]` = redacted timeline export (md/html/pdf).
set "SK=%USERPROFILE%\.agents\skills\workflow-monitor"
if /I "%~1"=="board" (
  python "%SK%\workflow_run.py"
  goto :eof
)
if /I "%~1"=="export" (
  pushd "%SK%" & python -m wfmon_export %* & popd
  goto :eof
)
python "%SK%\workflow_monitor.py" %*
