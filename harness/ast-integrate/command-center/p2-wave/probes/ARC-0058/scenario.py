"""Executable evidence-or-cut scenario for ARC-0058.

Both-states:
  LIVE ledger  -> mix of ERROR-REDUCING and COSMETIC; ranking computed
  EMPTY ledger -> every item COSMETIC (evidence-or-cut, never UNPROVEN)
  UNPROVEN mutant of a zero-count item must be rejected
"""
from __future__ import annotations

from typing import Any

import classifier as C
import ledger as L


def run_scenario() -> dict[str, Any]:
    observations = L.collect_observations()
    tally = L.tally_by_class(observations)
    live = C.classify_live(tally)
    empty = C.classify_live({})
    mutant_items = [dict(r) for r in (empty.get("items") or [])]
    if not mutant_items:
        mutant_ok, mutant_why = True, "empty-items"
    else:
        mutant_items[0]["class"] = "UNPROVEN"
        mutant_ok, mutant_why = C.reject_unproven(mutant_items)

    empty_items = empty.get("items") or []
    empty_all_cosmetic = bool(empty_items) and all(
        r.get("class") == "COSMETIC" and int(r.get("occurrence_count") or 0) == 0
        for r in empty_items
    )
    empty_unproven = any(r.get("class") == "UNPROVEN" for r in empty_items)
    ranked = live.get("surviving_ranked") or []
    live_ok = live.get("ok") is True and empty.get("ok") is True
    mixed = bool(live.get("cosmetic_ids")) and bool(ranked)
    funds_cosmetic = live.get("organizing_principle_would_fund_cosmetic") is True
    passed = (
        live_ok
        and mixed
        and funds_cosmetic
        and empty_all_cosmetic
        and not empty_unproven
        and mutant_ok is False
        and len(ranked) >= 1
    )
    return {
        "pass": passed,
        "live": live,
        "empty_ledger": empty,
        "empty_all_cosmetic": empty_all_cosmetic,
        "empty_unproven_present": empty_unproven,
        "unproven_rejected": mutant_ok is False,
        "unproven_why": mutant_why,
        "tally": tally,
        "observations": [
            {k: o[k] for k in o if k != "instances"} for o in observations
        ],
        "ranked_ids": [r["id"] for r in ranked],
        "cosmetic_ids": list(live.get("cosmetic_ids") or []),
        "organizing_principle_would_fund_cosmetic": funds_cosmetic,
        "computed_not_asserted": True,
    }


if __name__ == "__main__":
    import json
    import sys

    result = run_scenario()
    print(json.dumps({k: result[k] for k in sorted(result)}, indent=2, sort_keys=True))
    if not result.get("pass"):
        print("FAILED:ARC-0058-scenario")
        raise SystemExit(1)
    print("SUCCESS:ARC-0058-scenario")
    raise SystemExit(0)
