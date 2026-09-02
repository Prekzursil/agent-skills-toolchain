#!/usr/bin/env python3
"""Probe 1 — scope: the guard reads the scope that actually takes effect.

Independent of probe 2 (budget). Two config states, two answers:
  * disable only at ~/.claude.json root → INERT; process table still shows spawn
  * disable at per-project block → EFFECTIVE; would_spawn is empty

The naive root-trust resolver is the negative control: it disagrees with the
process table. The guard must agree with the process table.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from mcp_process_guard.guard import evaluate_new_tier  # noqa: E402
from mcp_process_guard.process_table import census, synthetic_stdio_table  # noqa: E402
from mcp_process_guard.scope import (  # noqa: E402
    SCOPE_CLAUDE_PROJECT,
    SCOPE_CLAUDE_ROOT,
    fixture_effective_project_disable,
    fixture_inert_root_disable,
    inert_root_disables,
    naive_trust_root_disable,
    resolve,
    would_spawn_names,
)

SERVERS = ("alpha", "beta", "gamma")


def main() -> int:
    root_cfg = fixture_inert_root_disable(SERVERS)
    project_cfg = fixture_effective_project_disable(SERVERS, disabled=SERVERS)
    root_spawn = would_spawn_names(root_cfg)
    project_spawn = would_spawn_names(project_cfg)
    if root_spawn == project_spawn:
        print("FAILED:IMP-0472-probe1 root-disable and project-disable produced the same answer")
        return 1
    if root_spawn != SERVERS:
        print(f"FAILED:IMP-0472-probe1 inert root disable still spawned {root_spawn}")
        return 1
    if project_spawn != ():
        print(f"FAILED:IMP-0472-probe1 project disable did not take effect: {project_spawn}")
        return 1

    rows = synthetic_stdio_table(2, SERVERS)
    snap = census(rows, source="probe1-injected-process-table")
    naive = naive_trust_root_disable(root_cfg)
    if naive == frozenset(SERVERS) and set(snap.by_server) == set(SERVERS):
        process_table_contradicts_naive = True
    else:
        print("FAILED:IMP-0472-probe1 process table did not contradict naive root trust")
        return 1
    if set(root_spawn) != set(snap.by_server):
        print("FAILED:IMP-0472-probe1 effective resolver disagrees with process table")
        return 1

    decision = evaluate_new_tier(rows, root_cfg, budget=256, transport="stdio-per-session")
    if decision.would_spawn != SERVERS or decision.inert_root_disables != SERVERS:
        print("FAILED:IMP-0472-probe1 guard treated inert root disable as effective")
        return 1
    if decision.extra != 3:
        print(f"FAILED:IMP-0472-probe1 extra={decision.extra} (expected 3 live servers)")
        return 1

    rec_alpha = resolve(root_cfg)["alpha"]
    rec_proj = resolve(project_cfg)["alpha"]
    payload = {
        "probe": "probe1-scope",
        "unit_id": "IMP-0472",
        "root_disable_scope": SCOPE_CLAUDE_ROOT,
        "project_disable_scope": SCOPE_CLAUDE_PROJECT,
        "root_disable_would_spawn": list(root_spawn),
        "project_disable_would_spawn": list(project_spawn),
        "answers_differ": True,
        "root_disable_inert": True,
        "project_disable_effective": rec_proj.effective_disabled,
        "alpha_root": rec_alpha.as_dict(),
        "alpha_project": rec_proj.as_dict(),
        "process_table": {
            "source": snap.source,
            "mcp_count": snap.mcp_count,
            "session_count": snap.session_count,
            "multiplier": snap.multiplier,
            "by_server": snap.by_server,
        },
        "naive_root_trust_disabled": sorted(naive),
        "process_table_contradicts_naive_root_trust": process_table_contradicts_naive,
        "guard_extra_after_inert_root_disable": decision.extra,
        "inert_root_disables": list(inert_root_disables(root_cfg)),
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"root_spawn={list(root_spawn)} project_spawn={list(project_spawn)} "
        f"differ=True process_table_mcp={snap.mcp_count} naive_contradicted=True"
    )
    print("SUCCESS:IMP-0472-probe1 scope: root disable inert; project disable effective; process table is source of truth")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
