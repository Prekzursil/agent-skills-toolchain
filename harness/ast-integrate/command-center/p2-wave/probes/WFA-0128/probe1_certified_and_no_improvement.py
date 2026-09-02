#!/usr/bin/env python3
"""Probe 1: both forge terminals are live, and a certified fusion rolls back.

A complementary pair must certify. A no-gain pair must return NO-IMPROVEMENT
naming the best source and the margin. Every certified fusion must decompose
to its sources and pass rollback rehearsal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from forge import (  # noqa: E402
    decompose,
    rollback_rehearsal,
    run_case,
    score,
    smoke_fingerprint,
)

ART = REPO / "command-center/wfa/WFA-0128-workflow-forge-executable-spec.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0128-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("primary artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(doc)
    if doc.get("unit_id") != "WFA-0128":
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:WFA-0128" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    complementary = json.loads((HERE / "fixtures" / "complementary.json").read_text(encoding="utf-8"))
    no_gain = json.loads((HERE / "fixtures" / "no-gain.json").read_text(encoding="utf-8"))

    certified = run_case(complementary)
    if certified.get("terminal") != "CERTIFIED-FUSION":
        return fail(f"complementary terminal={certified.get('terminal')} reason={certified.get('reason')}")
    fusion = certified["fusion"]
    sources = complementary["candidates"]
    if certified["margin"] < certified["margin_floor"]:
        return fail("certified margin below floor")
    if score(fusion, complementary["goal"]) <= max(score(s, complementary["goal"]) for s in sources):
        return fail("fusion does not beat best source")
    restored = decompose(fusion)
    if set(restored) != {s["id"] for s in sources}:
        return fail(f"decompose ids {sorted(restored)}")
    rehearsal = rollback_rehearsal(fusion, sources)
    if not rehearsal["pass"]:
        return fail(f"rollback {json.dumps(rehearsal)}")
    for src in sources:
        want = smoke_fingerprint(
            {"id": src["id"], "mechanisms": src["mechanisms"], "stages": src["stages"]}
        )
        got = smoke_fingerprint(restored[src["id"]])
        if want != got:
            return fail(f"smoke mismatch {src['id']}")

    declined = run_case(no_gain)
    if declined.get("terminal") != "NO-IMPROVEMENT":
        return fail(f"no-gain terminal={declined.get('terminal')}")
    if declined.get("best_source_id") != "src-full-strong":
        return fail(f"best_source_id={declined.get('best_source_id')}")
    if "margin" not in declined or declined["margin"] is None:
        return fail("no-gain margin missing")
    if declined.get("reason") != "MARGIN_BELOW_FLOOR":
        return fail(f"no-gain reason={declined.get('reason')}")

    print(
        json.dumps(
            {
                "probe": "probe1-certified-and-no-improvement",
                "unit_id": "WFA-0128",
                "certified_terminal": certified["terminal"],
                "certified_operator": certified.get("operator"),
                "certified_margin": certified["margin"],
                "rollback_pass": rehearsal["pass"],
                "decomposed_ids": sorted(restored),
                "no_gain_terminal": declined["terminal"],
                "no_gain_best_source_id": declined["best_source_id"],
                "no_gain_margin": declined["margin"],
                "both_terminals_valid": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0128-probe1 certified fusion, rollback rehearsal, no-improvement names best source and margin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
