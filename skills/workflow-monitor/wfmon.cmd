@echo off
rem wfmon — launch the whole-fleet workflow-monitor cockpit.  `wfmon board` = plain-text board.
set "SK=%USERPROFILE%\.agents\skills\workflow-monitor"
if /I "%~1"=="board" (
  python "%SK%\workflow_run.py"
  goto :eof
)
python "%SK%\workflow_monitor.py" %*
