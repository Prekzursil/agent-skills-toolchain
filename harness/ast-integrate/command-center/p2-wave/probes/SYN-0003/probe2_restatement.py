#!/usr/bin/env python3
"""Probe 2: restatement gate, runnable probes, planted defects FIRE; live SILENT."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gate  # noqa: E402
import generate as G  # noqa: E402

ART = G.REPO / "command-center/synthesis/SYN-0003.rival-explanations.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0003-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    records = copy.deepcopy(doc.get("records") or [])
    rivals = [r for r in records if r.get("label") == "RIVAL"]
    if not rivals:
        return fail("no RIVAL records to gate")

    # Known-present restatement (paraphrase of the cause) must FIRE first.
    planted_rest = copy.deepcopy(records)
    target = next(r for r in planted_rest if r.get("label") == "RIVAL")
    target["rival_statement"] = target["cause_statement"]
    rest_hits = gate.restatement_hits(planted_rest)
    print("detector_control_first=True")
    print(f"planted_restatement_hits={len(rest_hits)}")
    if not rest_hits:
        return fail("planted restatement did not FIRE")
    print("detector_control_found_known_present=True")

    planted_cmd = copy.deepcopy(records)
    t2 = next(r for r in planted_cmd if r.get("label") == "RIVAL")
    t2["experiment"] = {
        "command": "python3 command-center/p2-wave/probes/SYN-0003/no-such-collector.py",
        "probe_path": "command-center/p2-wave/probes/SYN-0003/no-such-collector.py",
        "runnable": True,
    }
    miss = gate.unrunnable_hits(planted_cmd, G.REPO)
    print(f"planted_missing_probe_hits={len(miss)}")
    if not miss:
        return fail("planted missing probe did not FIRE")

    planted_nd = copy.deepcopy(records)
    t3 = next(r for r in planted_nd if r.get("label") == "RIVAL")
    t3["discriminating_observation"] = t3["shared_observation"]
    nd = gate.non_discriminating_hits(planted_nd)
    print(f"planted_non_discriminating={nd}")
    if not nd:
        return fail("planted non-discriminating experiment did not FIRE")

    live_rest = gate.restatement_hits(records)
    live_nd = gate.non_discriminating_hits(records)
    live_unrun = gate.unrunnable_hits(records, G.REPO)
    print(
        f"live_restatement={len(live_rest)} live_non_disc={live_nd} "
        f"live_unrunnable={len(live_unrun)}"
    )
    if live_rest:
        return fail(f"live restatement {live_rest}")
    if live_nd:
        return fail(f"live non-discriminating {live_nd}")
    if live_unrun:
        return fail(f"live unrunnable {live_unrun}")

    # Re-derive from hierarchy + records without reading doc['state'].
    hier = G.load_hierarchy()
    cov = gate.coverage([c["id"] for c in hier["causes"]], records)
    if not cov["ok"]:
        return fail("re-derived coverage failed")
    print("reviewer_rederived_without_state=True")
    print("SUCCESS:SYN-0003-probe2 restatement runnable planted-controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
