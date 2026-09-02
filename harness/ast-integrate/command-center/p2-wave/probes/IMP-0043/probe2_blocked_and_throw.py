#!/usr/bin/env python3
"""Probe 2: independent reviewer of aggregate honesty (evidence signal 2).

Catalog evidence (2): the same runner with one probe forced BLOCKED must
flip the aggregate to not-healthy. Also: a throwing probe is FAILED (never
healthy), and a registered-but-unrun probe is not pass.

This file does not import probe1. It plants its own fixtures and constructs
its own registry so the two signals are independent runs.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
import health_check as hc  # noqa: E402
import health_probes as hp  # noqa: E402


class ThrowingProbe:
    probe_id = "reviewer_throw"

    def __init__(self) -> None:
        self.both_states = hc.BothStatesControl(
            unit_id="IMP-0044",
            known_good="n/a",
            known_broken="raises",
            expected_good="SUCCESS",
            expected_broken="FAILED",
            plant_good=hp.plant_healthy_tree,
            plant_broken=hp.plant_healthy_tree,
        )

    def run(self, ctx: hc.HealthContext) -> hc.ProbeResult:
        raise RuntimeError("reviewer-forced-throw")


def main() -> int:
    fail = False
    with tempfile.TemporaryDirectory(prefix="imp0043-p2-") as td:
        root = Path(td)
        hp.plant_healthy_tree(root)
        registry = hc.default_registry()

        healthy = hc.run_all(registry, hc.HealthContext(root=root))
        blocked = hc.run_all(
            registry,
            hc.HealthContext(root=root, force_state={"hooks_loaded": "BLOCKED"}),
        )
        print(
            json.dumps(
                {
                    "healthy_run": {
                        "healthy": healthy.healthy,
                        "aggregate": healthy.aggregate,
                        "reason": healthy.reason,
                    },
                    "blocked_run": {
                        "healthy": blocked.healthy,
                        "aggregate": blocked.aggregate,
                        "reason": blocked.reason,
                        "blocked_ids": blocked.blocked_ids,
                    },
                },
                sort_keys=True,
            )
        )
        if not healthy.healthy:
            print("FAILED:IMP-0043-probe2 control healthy run was not healthy")
            fail = True
        if blocked.healthy:
            print("FAILED:IMP-0043-probe2 BLOCKED run stayed healthy (overclaim)")
            fail = True
        if "hooks_loaded" not in blocked.blocked_ids:
            print("FAILED:IMP-0043-probe2 blocked_ids missing hooks_loaded")
            fail = True
        if healthy.healthy == blocked.healthy:
            print("FAILED:IMP-0043-probe2 aggregate did not flip")
            fail = True

        registry_throw = hc.default_registry()
        registry_throw.register(ThrowingProbe())
        thrown = hc.run_all(registry_throw, hc.HealthContext(root=root))
        throw_row = next(r for r in thrown.probes if r.probe_id == "reviewer_throw")
        print(
            f"throw state={throw_row.state} uncaught={throw_row.evidence.get('uncaught')} "
            f"healthy={thrown.healthy}"
        )
        if throw_row.state != "FAILED" or thrown.healthy or throw_row.evidence.get("uncaught") is not True:
            print("FAILED:IMP-0043-probe2 throw was swallowed or not FAILED")
            fail = True

        partial = [row for row in healthy.probes if row.probe_id != "mcp_reachable"]
        unrun = hc.aggregate(registry, partial)
        print(
            f"unrun missing={unrun.missing_unrun} healthy={unrun.healthy} "
            f"reason={unrun.reason}"
        )
        if unrun.healthy or unrun.missing_unrun != ["mcp_reachable"]:
            print("FAILED:IMP-0043-probe2 unrun treated as pass")
            fail = True

        rows = registry.require_both_states()
        if len(rows) != len(hp.REQUIRED_PROBE_IDS):
            print(f"FAILED:IMP-0043-probe2 both-states rows={len(rows)}")
            fail = True
        else:
            print(f"both-states registered={len(rows)} unit=IMP-0044")

    if fail:
        print("FAILED:IMP-0043-probe2 blocked/throw/unrun reviewer")
        return 1
    print("SUCCESS:IMP-0043-probe2 blocked flips aggregate; throw=FAILED; unrun is not pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
