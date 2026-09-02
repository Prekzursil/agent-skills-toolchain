#!/usr/bin/env python3
"""Probe 2: independent reviewer re-runs V-GRAPH both-states in scratch."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402
import schema_local as S  # noqa: E402

ART = C.REPO / C.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0040-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    sentinel = C.catalog_sentinel()
    if sentinel not in text:
        return fail("completion_sentinel absent")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        return fail("reviewer not independent")
    scope = str(reviewer.get("scope") or reviewer.get("notes") or "")
    if "detector control" not in scope.lower():
        return fail("reviewer scope is not detector-control")

    live = C.measure()
    gate = live["gate"]
    print(
        json.dumps(
            {
                "clean_exit": gate["clean_exit"],
                "regen_exit": gate["regen_exit"],
                "mutated_exit": gate["mutated_exit"],
                "mutated_vgraph": gate["mutated_vgraph"],
                "stale_exit": gate["stale_exit"],
                "stale_vgraph": gate["stale_vgraph"],
                "mutation": gate["mutation"],
                "live_register_present": live["live_register_present"],
                "ok": live["ok"],
            },
            sort_keys=True,
        )
    )
    if gate["clean_exit"] != 0:
        return fail(f"unmodified pair exit {gate['clean_exit']} (want 0)")
    if gate["regen_exit"] != 0:
        return fail(f"regenerated pair exit {gate['regen_exit']} (want 0)")
    if gate["mutated_exit"] == 0:
        return fail("one-byte catalog mutation did not turn the gate red")
    if not gate["mutated_vgraph"]:
        return fail("mutated catalog did not emit V-GRAPH")
    if gate["stale_exit"] == 0 or not gate["stale_vgraph"]:
        return fail("stale edge_count graph did not turn V-GRAPH red")
    if gate["mutation"].get("bytes_changed") != 1:
        return fail("mutation is not recorded as one byte")

    recorded = S.folded_measurement(doc).get("gate") or {}
    if recorded.get("clean_exit") != 0:
        return fail("artifact clean_exit is not 0")
    if recorded.get("mutated_exit") in (0, None):
        return fail("artifact mutated_exit is not red")
    if recorded.get("mutated_vgraph") is not True:
        return fail("artifact mutated_vgraph is not true")

    dc = S.folded_detector_control(doc)
    if dc.get("known_broken_fired") is not True:
        return fail("detector_control.known_broken_fired is not true")
    if int(dc.get("known_healthy_silent_count") or 0) < 2:
        return fail("known_healthy_silent_count < 2")

    print(
        f"reviewer_id={reviewer.get('reviewer_id')} "
        f"clean={gate['clean_exit']} mutated={gate['mutated_exit']} "
        f"stale={gate['stale_exit']} vgraph=True"
    )
    print("SUCCESS:AUD-0040-probe2 detector-control both-states re-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
