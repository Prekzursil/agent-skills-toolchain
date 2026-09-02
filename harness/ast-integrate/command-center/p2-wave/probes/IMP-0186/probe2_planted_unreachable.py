#!/usr/bin/env python3
"""Probe 2: planted unreachable branch is detected (detector control).

Four planted fixtures (never, out-of-enum, subsumed, contradiction) must:
  * be flagged by dual_reachability (named dead id in unreachable)
  * be REFUSED by emit_conditional_hybrid with unreachable-branch
The good twin must stay silent (0 unreachable, emit succeeds). A detector
that returns empty on both the plant and the twin is not measuring.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from workflow_fusion.conditional_hybrid import (  # noqa: E402
    FusionRefused,
    analyze_conditional_hybrid,
    emit_conditional_hybrid,
)
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0186.json"
UNIT = "IMP-0186"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    good = S.good_spec()
    good_proof = analyze_conditional_hybrid(good)
    if good_proof.unreachable:
        return fail(f"good twin flagged {list(good_proof.unreachable)}")
    try:
        emit_conditional_hybrid(good)
    except FusionRefused as exc:
        return fail(f"good twin emit refused: {exc}")

    rows = []
    for name, (factory, dead_id) in S.PLANTS.items():
        spec = factory()
        proof = analyze_conditional_hybrid(spec)
        if dead_id not in proof.unreachable:
            return fail(
                f"plant {name}: dead id {dead_id} not in unreachable={list(proof.unreachable)}"
            )
        if not proof.unreachable:
            return fail(f"plant {name}: detector silent")
        refused = False
        code = ""
        try:
            emit_conditional_hybrid(spec)
        except FusionRefused as exc:
            refused = True
            code = exc.code
        if not refused:
            return fail(f"plant {name}: emit accepted a dead branch")
        if code != "fusion.conditional_hybrid.unreachable-branch":
            return fail(f"plant {name}: refuse code {code}")
        rows.append(
            {
                "plant": name,
                "dead_id": dead_id,
                "unreachable": list(proof.unreachable),
                "refused": True,
                "code": code,
            }
        )

    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    controls = doc.get("negative_controls") or []
    fired = [c for c in controls if c.get("fired_on_bad_state") is True]
    silent = [c for c in controls if c.get("silent_on_good_state") is True]
    if len(fired) < 1 or len(silent) < 1:
        return fail("receipt missing both-states negative_controls")

    report = {
        "probe": "probe2-planted-unreachable",
        "unit_id": UNIT,
        "pass": True,
        "good_unreachable": [],
        "good_emit_ok": True,
        "plants": rows,
        "plants_detected": len(rows),
        "plants_expected": len(S.PLANTS),
    }
    print(json.dumps(report, sort_keys=True))
    print(f"plants_detected={len(rows)}/{len(S.PLANTS)} good_silent=True")
    print("SUCCESS:IMP-0186-probe2 planted unreachable branch is detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
