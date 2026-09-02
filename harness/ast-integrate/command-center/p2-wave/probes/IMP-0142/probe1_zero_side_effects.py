#!/usr/bin/env python3
"""Probe 1: dry-run of the largest fixture has zero spawns and zero egress.

Instruments: CountingFakeRail.spawn_count and NetAllowlistShim.egress_count
(not prose). Also: routing/params/cardinality/cost are resolved; writes stay
inside scratch; a canary outside scratch is byte-identical.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS / "agentrail"))
sys.path.insert(0, str(TOOLS / "agentspec"))
sys.path.insert(0, str(HERE))

from agentrail.ports import (  # noqa: E402
    CountingFakeRail,
    InstrumentedPorts,
    SpawnForbidden,
    WriteOutsideScratch,
)
from agentspec.dispatchpolicy import dry_run  # noqa: E402
from largest import dry_run_params, largest_workflow  # noqa: E402

OUT = HERE / "probe1-zero-side-effects.raw.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    wf = largest_workflow()
    params = dry_run_params()
    with tempfile.TemporaryDirectory(prefix="imp0142-p1-") as tmp:
        scratch = Path(tmp) / "scratch"
        outside = Path(tmp) / "canary.txt"
        outside.write_text("do-not-touch\n", encoding="utf-8")
        before = {
            "sha256": _sha(outside),
            "mtime_ns": outside.stat().st_mtime_ns,
            "size": outside.stat().st_size,
        }
        ports = InstrumentedPorts.for_dry_run(scratch)
        plan = dry_run(wf, params, ports=ports)
        after = {
            "sha256": _sha(outside),
            "mtime_ns": outside.stat().st_mtime_ns,
            "size": outside.stat().st_size,
        }

        writes = list(ports.fs.writes) if ports.fs is not None else []
        writes_under_scratch = all(
            Path(w).resolve().is_relative_to(scratch.resolve()) for w in writes
        )
        outside_write_refused = False
        if ports.fs is not None:
            try:
                ports.fs.write_text("../escape.txt", "nope")
            except WriteOutsideScratch:
                outside_write_refused = True

        # Instrument both-states: the counter is not stuck at zero.
        probe = CountingFakeRail(forbid_spawn=True)
        try:
            probe.spawn(["instrument-control"])
        except SpawnForbidden:
            pass
        instrument_counts = probe.spawn_count == 1

        routing_ok = len(plan.routing) == 64 and all(
            r.get("vendor") and r.get("model") and r.get("rail") for r in plan.routing
        )
        params_ok = (
            plan.params.get("region") == "eu"
            and plan.params.get("batch_size") == 16
            and isinstance(plan.params.get("api_token"), dict)
            and plan.params["api_token"].get("kind") == "secret_ref"
            and "sk-" not in json.dumps(plan.params["api_token"])
        )
        card = plan.cardinality
        cardinality_ok = (
            len(card) == 4
            and all(c["width"] == 16 and c["max_cardinality"] == 16 for c in card)
        )
        cost_ok = int(plan.cost.get("total_micro_usd") or 0) > 0 and plan.cost.get(
            "unit_count"
        ) == 64
        canary_ok = before == after
        zero_ok = ports.zero_spawns() and ports.zero_egress()
        passed = bool(
            zero_ok
            and canary_ok
            and writes_under_scratch
            and outside_write_refused
            and instrument_counts
            and routing_ok
            and params_ok
            and cardinality_ok
            and cost_ok
            and plan.spawn_count == 0
            and plan.egress_count == 0
        )
        doc = {
            "probe": "probe1-zero-side-effects",
            "unit_id": "IMP-0142",
            "workflow_id": plan.workflow_id,
            "planned_units": len(plan.planned_units),
            "spawn_count": plan.spawn_count,
            "egress_count": plan.egress_count,
            "rail_spawn_count": ports.rail.spawn_count,
            "net_egress_count": ports.net.egress_count,
            "writes": writes,
            "writes_under_scratch": writes_under_scratch,
            "outside_write_refused": outside_write_refused,
            "canary_unchanged": canary_ok,
            "instrument_counts_when_spawned": instrument_counts,
            "routing_resolved": routing_ok,
            "params_resolved": params_ok,
            "cardinality_ok": cardinality_ok,
            "cost_ok": cost_ok,
            "cost_total_micro_usd": plan.cost.get("total_micro_usd"),
            "pass": passed,
        }
        OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            f"spawns={plan.spawn_count} egress={plan.egress_count} "
            f"units={len(plan.planned_units)} cost={plan.cost.get('total_micro_usd')} "
            f"canary_ok={canary_ok} writes_scratch={writes_under_scratch} "
            f"outside_refused={outside_write_refused} instrument={instrument_counts}"
        )
        if not passed:
            print("FAILED:IMP-0142-probe1 zero-side-effect dry-run")
            print(json.dumps(doc, indent=2, sort_keys=True)[:2000])
            return 1
        print("SUCCESS:IMP-0142-probe1 zero spawns and zero egress on largest fixture")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
