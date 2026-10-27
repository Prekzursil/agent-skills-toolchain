@echo off
rem mon <name> [args] -- launch a registered monitor from monitors.toml.
rem
rem THIN SHIM: the registry loader, trigger-match, and launch-argv builder all live in the
rem 100%-gated `monitorcore.monitors` core; this .cmd only puts the vendored monitorcore package
rem (shipped inside the workflow-monitor skill) on PYTHONPATH and hands off. The generalized
rem replacement for the old wfmon-only launcher; wfmon/agentmon delegate here.
rem
rem This dir (~/.agents/skills/monitor-launcher) must be on PATH for `mon` to resolve.
setlocal
set "WFMON=%USERPROFILE%\.agents\skills\workflow-monitor"
if defined PYTHONPATH (
  set "PYTHONPATH=%WFMON%;%PYTHONPATH%"
) else (
  set "PYTHONPATH=%WFMON%"
)
python -m monitorcore.monitors %*
endlocal
