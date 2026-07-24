@echo off
REM mon crcp entry ? always uses live tools/crcp package
set "CRP=%USERPROFILE%\source\agent-skills-toolchain\tools\crcp"
set "PYTHONPATH=%CRP%;%PYTHONPATH%"
python "%CRP%\monitor\crcp_health_monitor.py" %*
