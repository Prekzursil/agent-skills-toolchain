#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
cands = [
    "command-center/expansion_proof.py",
    "command-center/confirmation/expansion_proof.py",
    "command-center/lib/expansion_proof.py",
    "tools/expansion_proof.py",
    "tools/launch_adapter.py",
    "tools/launch_adapter/__init__.py",
    "tools/pr_only_guard.py",
    "tools/pr_only_guard/__init__.py",
    "tools/agentspec/checkpoint.py",
    "tools/agentspec/agentspec/checkpoint.py",
    "tools/agentspec-js/parity/run.py",
    "tools/agentrail/test_no_rival_core.py",
    "tools/monitor.py",
    "tools/monitor/__init__.py",
    "tools/blueprint_library/__init__.py",
    "tools/blueprint_library/compiler.py",
    "tools/council/integrity/dupes.py",
    "tools/council/vote/ballots.py",
    "tools/council/calibration/report.py",
    "tools/council/participants/memory.py",
    "tools/selfimprove/writeback.py",
    "tools/selfimprove/__init__.py",
    "command-center/lib/__init__.py",
    "command-center/lib/completion_reducer.py",
    "tools/lib/completion_reducer.py",
    "tools/headroom_guard/guard.py",
    "tools/mcp_process_guard/guard.py",
    "tools/package_hygiene.py",
    "tools/package_hygiene/__init__.py",
    "command-center/p2-wave/probes/TST-0254/dry_run_workflow.py",
    "tools/monitorcore/monitorcore/cockpit.py",
    "tools/agentspec/spec.py",
    "tools/agentspec/agentspec/spec.py",
    "tools/marketplace/lockfile.py",
    "command-center/schema/artifact.schema.json",
    "platform/schema/artifact.schema.json",
    "tools/workflow_foundry/__init__.py",
    "command-center/p2-wave/probes/ADV-0059/probe1.py",
    "command-center/p2-wave/probes/ADV-0059/probe1_drift.py",
    "command-center/p2-wave/seed-stage/p2_jsonschema_hook.py",
    "command-center/p2-wave/seed-stage/g1_python.py",
]
print("REPO", REPO)
for rel in cands:
    p = REPO / rel
    print(f"{'Y' if p.is_file() else 'N'} {rel} {p.stat().st_size if p.is_file() else 0}")
