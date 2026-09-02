#!/usr/bin/env python3
"""Probe 2: guard-removal mutations turn at least three named tests red.

Independent reviewer names one mutation the suite would NOT catch (homoglyph
typosquat). This probe does not rebuild A3 DESIGN.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import schema_util as SU  # noqa: E402
import suite as S  # noqa: E402

ART = REPO / "command-center/phase3/A3/TEST-PLAN.json"
UNCAUGHT = "M-HOMOGLYPH-TYPOSQUAT"


def main() -> int:
    greens = [S.run_one(spec) for spec in S.NAMED]
    bad = [g["id"] for g in greens if not g.get("pass")]
    if bad:
        print(f"FAILED:ARC-0022-probe2 named suite red with guards {bad}")
        for g in greens:
            if not g.get("pass"):
                print(f"  {g['id']} why={g.get('why')} state={g.get('state')}")
        return 1

    muts = S.guard_mutations()
    turned = [m for m in muts if m.get("turns_red")]
    if len(turned) < 3:
        print(f"FAILED:ARC-0022-probe2 turns_red={len(turned)} want>=3")
        for m in muts:
            print(
                f"  {m['test_id']} guard={m['guard_removed']} "
                f"green={m['green_with_guard']} red={m['red_without_guard']} why={m['red_why']}"
            )
        return 1
    still_green = [m for m in muts if m.get("green_with_guard") and not m.get("red_without_guard")]
    if still_green:
        print("FAILED:ARC-0022-probe2 mutation-survives")
        for m in still_green:
            print(f"  {m['test_id']} still green after removing {m['guard_removed']}")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0022-probe2 TEST-PLAN.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:ARC-0022" not in json.dumps(doc):
        print("FAILED:ARC-0022-probe2 sentinel absent")
        return 1
    body = SU.payload(doc)
    art_muts = body.get("guard_removal_mutations") or []
    if len(art_muts) < 3:
        print(f"FAILED:ARC-0022-probe2 artifact mutations {len(art_muts)}")
        return 1
    art_red = [m for m in art_muts if isinstance(m, dict) and m.get("turns_red") is True]
    if len(art_red) < 3:
        print("FAILED:ARC-0022-probe2 artifact turns_red < 3")
        return 1
    reviewer = doc.get("reviewer") or {}
    blob = json.dumps(reviewer) + json.dumps(body.get("uncaught_mutation") or {})
    if UNCAUGHT not in blob and "homoglyph" not in blob.lower() and "typosquat" not in blob.lower():
        print("FAILED:ARC-0022-probe2 reviewer uncaught mutation not named")
        return 1
    if reviewer.get("independent") is not True:
        print("FAILED:ARC-0022-probe2 reviewer not independent")
        return 1
    ncs = doc.get("negative_controls") or []
    if len(ncs) < 3:
        print(f"FAILED:ARC-0022-probe2 negative_controls {len(ncs)}")
        return 1

    out = {
        "probe": "probe2-guard-mutations",
        "unit_id": "ARC-0022",
        "named_green": len(greens),
        "mutations": len(muts),
        "turns_red": len(turned),
        "red_ids": [m["test_id"] for m in turned],
        "uncaught_named": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(f"guard_mutations turns_red={len(turned)}/{len(muts)}")
    print("SUCCESS:ARC-0022-probe2 guard-removal mutations turn the suite red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
