#!/usr/bin/env python3
"""Probe 1: mention-only yields 0; USE yields >=1 (both-states).

The mention-only control is written so a naive keyword matcher DOES fire.
The live adapter must stay silent. Disabling use-vs-mention must harvest
the mention document — proving the filter is load-bearing, not a no-op.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import corpus as C  # noqa: E402
from workflow_scout.adapters import prose as P  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0153.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def check_receipt() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable {exc}"
    if not isinstance(doc, dict):
        return "receipt not an object"
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return f"self-declared {doc.get('state')}"
    if "SUCCESS:IMP-0153" not in text:
        return "sentinel absent"
    if doc.get("unit_id") != "IMP-0153":
        return f"unit_id {doc.get('unit_id')}"
    return None


def main() -> int:
    C.materialize()
    impl = {P.norm_id(x) for x in C.IMPLEMENTED_IDS}
    mention = (HERE / "fixtures/controls/mention-only.md").read_text(encoding="utf-8")
    use = (HERE / "fixtures/controls/use.md").read_text(encoding="utf-8")

    men_live = P.harvestable(
        P.mine_text(
            mention,
            source_path="fixtures/controls/mention-only.md",
            implemented=impl,
            distinguish_use_mention=True,
        )
    )
    use_live = P.harvestable(
        P.mine_text(
            use,
            source_path="fixtures/controls/use.md",
            implemented=impl,
            distinguish_use_mention=True,
        )
    )
    naive = P.naive_keyword_hits(mention)
    mutant = P.harvestable(
        P.mine_text(
            mention,
            source_path="fixtures/controls/mention-only.md",
            implemented=impl,
            distinguish_use_mention=False,
        )
    )

    if men_live:
        print("FAILED:IMP-0153-probe1 mention-only harvested")
        print(json.dumps([c.__dict__ for c in men_live], indent=2)[:2000])
        return 1
    if len(use_live) < 1:
        print("FAILED:IMP-0153-probe1 use control yielded 0 candidates")
        return 1
    if "imp0153-alpha-normalizer" not in {c.workflow_id for c in use_live}:
        print(
            "FAILED:IMP-0153-probe1 use ids "
            f"{sorted(c.workflow_id for c in use_live)}"
        )
        return 1
    if not naive:
        print("FAILED:IMP-0153-probe1 naive matcher silent on mention-only")
        return 1
    if not mutant:
        print("FAILED:IMP-0153-probe1 mutant did not harvest mention-only")
        return 1
    rec_err = check_receipt()
    if rec_err:
        print(f"FAILED:IMP-0153-probe1 {rec_err}")
        return 1

    payload = {
        "mention_only_harvest": 0,
        "use_harvest": len(use_live),
        "use_ids": sorted({c.workflow_id for c in use_live}),
        "naive_mention_hits": naive,
        "mutant_mention_harvest": sorted({c.workflow_id for c in mutant}),
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "pass": True,
        "probe": "probe1-both-states-use-vs-mention",
        "unit_id": "IMP-0153",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:IMP-0153-probe1 mention-only=0 use>=1; naive and mutant fire"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
