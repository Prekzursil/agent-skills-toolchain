#!/bin/bash
cd /home/prekzursil/p2-g1
sed -n '330,334p' tools/editor/ralph-orchestrator/vendor/tools/e2e/tui_visual_regression.py
echo ----185
sed -n '183,190p' tools/monitorcore/monitorcore/agent_tail.py
echo ----296
sed -n '293,302p' tools/monitorcore/monitorcore/agent_tail.py
echo ----app106
sed -n '103,109p' tools/taskwatch_monitor/cli/app.py
echo ----triage336
sed -n '333,339p' tools/triage-router/test_triage_router.py
echo ----fp111
sed -n '108,113p' tools/workspace-hooks/anti-degen/test_fingerprint.py
echo ----reinject
sed -n '108,132p' tools/workspace-hooks/goal-reinject/test_reinject.py
