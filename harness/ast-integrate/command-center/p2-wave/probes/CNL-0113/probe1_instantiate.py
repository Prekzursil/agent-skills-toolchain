#!/usr/bin/env python3
"""Probe 1: instantiate both jury presets against the fixture task."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0113-jury-family-evidence-adjudication-and-benchmark-results-ju.md"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0113-probe1 {msg}")
    return 1


def main() -> int:
    j01 = E.evidence_adjudication_preset()
    j02 = E.benchmark_results_preset()
    task = json.loads((HERE / "fixtures" / "task.json").read_text(encoding="utf-8"))
    i01 = E.instantiate(j01, task)
    i02 = E.instantiate(j02, task)
    p01, p02 = E.profile_of(i01), E.profile_of(i02)
    print(f"C-J01 roster={p01['roster']}")
    print(f"C-J01 protocol_schedule={p01['protocol_schedule']}")
    print(f"C-J01 voting_method={p01['voting_method']}")
    print(f"C-J01 stopping_expression={p01['stopping_expression']}")
    print(f"C-J02 roster={p02['roster']}")
    print(f"C-J02 protocol_schedule={p02['protocol_schedule']}")
    print(f"C-J02 voting_method={p02['voting_method']}")
    print(f"C-J02 stopping_expression={p02['stopping_expression']}")
    if p01 == p02:
        return fail("profiles-identical")
    if "replicator" not in p02["roster"] or "metric-adversary" not in p02["roster"]:
        return fail("C-J02-missing-extra-roles")
    if "seal-protocol-before-result" not in p02["protocol_schedule"]:
        return fail("C-J02-missing-seal-step")
    if "replicator-or-canary" not in p02["voting_method"]:
        return fail("C-J02-missing-oracle-veto")
    if "CONFIRMED-while-replication-pending" not in p02["stopping_expression"]:
        return fail("C-J02-missing-forbid-confirmed-pending")
    sens01 = E.presenter_sensitivity(j01, task)
    sens02 = E.presenter_sensitivity(j02, task)
    print(f"C-J01 presenter_moved={sens01['verdict_moved']} outcomes={sens01['outcomes']}")
    print(f"C-J02 presenter_moved={sens02['verdict_moved']} outcomes={sens02['outcomes']}")
    if not sens01["verdict_moved"]:
        return fail("C-J01-should-track-presenter-packet")
    if sens02["verdict_moved"]:
        return fail("C-J02-must-not-move-to-confirmed-on-presenter-packet")
    if any(o["outcome"] == "CONFIRMED-UNDER-PROTOCOL" for o in sens02["outcomes"]):
        return fail("C-J02-confirmed-without-replication")
    art = E.REPO / OUT_REL
    if not art.is_file():
        return fail("artifact-missing")
    doc = json.loads(art.read_text(encoding="utf-8"))
    live = {p["preset_id"]: p for p in doc["instantiation"]["profiles"]}
    if live.get("C-J01") != p01 or live.get("C-J02") != p02:
        return fail("artifact-profile-stale")
    print("SUCCESS:CNL-0113-probe1 instantiate fixture profiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
