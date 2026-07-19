@echo off
rem agentmon [args] -- thin alias for `mon agentmon`. Opens one live tail terminal per active
rem Claude Code subagent (the agent-domain monitor). All logic lives in the generalized `mon`
rem launcher + monitorcore; this only forwards. Requires `mon` on PATH (same monitor-launcher dir).
call mon agentmon %*
