#!/usr/bin/env python3
"""Probe 2: known-bad fusion (mechanism conflict) must return NO-IMPROVEMENT.

A forge that always emits a fusion is a fusion generator. The control pair
carries a scheduler.central vs scheduler.distributed conflict. The real forge
must refuse construction. A naive always-fuse constructor must still produce
a fusion object on the same pair, proving the refusal is the decision, not
an inability to concatenate stages.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from forge import naive_always_fuse, preconditions, run_case  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0128-probe2 {msg}")
    return 1


def main() -> int:
    case = json.loads((HERE / "fixtures" / "known-bad-conflict.json").read_text(encoding="utf-8"))
    a, b = case["candidates"]
    pre = preconditions(a, b)
    if pre["legal"]:
        return fail("planted conflict pair was scored legal")
    if not pre["mechanism_conflicts"] and not pre["duplicate_control_plane"]:
        return fail("planted pair has no conflict signal")

    naive = naive_always_fuse(a, b)
    if naive.get("kind") != "fusion":
        return fail("naive always-fuse did not return a fusion (control is dead)")
    if naive.get("operator") != "union":
        return fail(f"naive operator={naive.get('operator')}")

    result = run_case(case)
    if result.get("terminal") != "NO-IMPROVEMENT":
        return fail(f"terminal={result.get('terminal')} (must not emit a fusion)")
    if result.get("fusion_attempted") is not False:
        return fail("conflict pair must not be constructed")
    if "MECHANISM_CONFLICT" not in str(result.get("reason") or "") and "DUPLICATE_CONTROL_PLANE" not in str(
        result.get("reason") or ""
    ):
        return fail(f"reason={result.get('reason')}")
    if result.get("best_source_id") != "src-central-scheduler":
        return fail(f"best_source_id={result.get('best_source_id')}")
    if result.get("margin") is None:
        return fail("margin missing on no-improvement record")
    if result.get("best_source_score") is None:
        return fail("best_source_score missing")

    print(
        json.dumps(
            {
                "probe": "probe2-known-bad-fusion",
                "unit_id": "WFA-0128",
                "preconditions_legal": pre["legal"],
                "mechanism_conflicts": pre["mechanism_conflicts"],
                "duplicate_control_plane": pre["duplicate_control_plane"],
                "naive_always_fuse_kind": naive.get("kind"),
                "forge_terminal": result["terminal"],
                "fusion_attempted": result["fusion_attempted"],
                "reason": result["reason"],
                "best_source_id": result["best_source_id"],
                "best_source_score": result["best_source_score"],
                "margin": result["margin"],
                "margin_definition": result["margin_definition"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0128-probe2 known-bad-fusion returns no-improvement naming best source and margin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
