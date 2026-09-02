#!/usr/bin/env python3
"""Probe 1: disappearing-idea — remove one synthesis citation and catch the gap.

Signal A is idea_id set-difference. Signal B is canonical_mechanism set-difference.
An independent recursive walk must recount the same missing counts. Duplicate
IDEA-0004 must not be required. A one-field ghost plant must make the two
signals disagree while still FIRING.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import ledger as L  # noqa: E402
import recount as R  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0056-idea-ledger-schema-and-per-participant-provenance.md"
)
GOOD = HERE / "fixtures/known-good.json"
DROP_ID = "IDEA-0003"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0056-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNL-0056":
        print("FAILED:CNL-0056-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:CNL-0056" not in text:
        print("FAILED:CNL-0056-probe1 sentinel absent")
        return 1
    schema = doc.get("idea_ledger_schema") or {}
    for key in ("originator", "duplicates", "supporters", "fate"):
        if key not in json.dumps(schema):
            print(f"FAILED:CNL-0056-probe1 schema missing {key}")
            return 1

    good = load(GOOD)
    baseline = L.check_disappearance(good)
    indep_good = R.tabulate(good)
    ok, why = R.numbers_agree(baseline, indep_good)
    if not baseline.get("silent") or baseline.get("fired"):
        print("FAILED:CNL-0056-probe1 known-good not silent", baseline)
        return 1
    if not ok:
        print("FAILED:CNL-0056-probe1 known-good recount", why)
        return 1
    if DROP_ID in (baseline["signal_a"].get("missing") or []):
        print("FAILED:CNL-0056-probe1 DROP_ID already missing on good")
        return 1
    if "IDEA-0004" in (baseline["signal_a"].get("required") or []):
        print("FAILED:CNL-0056-probe1 duplicate treated as required")
        return 1

    planted = L.drop_idea_from_synthesis(good, DROP_ID)
    dropped = L.check_disappearance(planted)
    indep_drop = R.tabulate(planted)
    ok_drop, why_drop = R.numbers_agree(dropped, indep_drop)
    a_miss = dropped["signal_a"].get("missing") or []
    b_miss = dropped["signal_b"].get("missing") or []
    caught = (
        dropped.get("fired") is True
        and not dropped.get("silent")
        and DROP_ID in a_miss
        and "mech.provenance.per-participant-origin" in b_miss
        and dropped["signal_a"]["n_missing"] == 1
        and dropped["signal_b"]["n_missing"] == 1
        and ok_drop
    )
    print(
        f"good silent={baseline.get('silent')} n_canonical={baseline.get('n_canonical')} "
        f"n_missing_ids={baseline['signal_a']['n_missing']}"
    )
    print(
        f"drop {DROP_ID} fired={dropped.get('fired')} "
        f"missing_ids={a_miss} missing_mechs={b_miss} "
        f"recount={why_drop}"
    )
    if not caught:
        print("FAILED:CNL-0056-probe1 disappearance not caught", dropped, why_drop)
        return 1

    ghost = copy.deepcopy(good)
    for node in ghost["synthesis"]["nodes"]:
        cites = list(node.get("cites_idea_ids") or [])
        if DROP_ID in cites:
            node["cites_idea_ids"] = [x for x in cites if x != DROP_ID]
    ghost_res = L.check_disappearance(ghost)
    ghost_ok = (
        ghost_res.get("fired") is True
        and ghost_res.get("signals_disagree") is True
        and DROP_ID in (ghost_res["signal_a"].get("missing") or [])
        and ghost_res["signal_b"].get("fires") is False
    )
    print(
        f"ghost_id_only fired={ghost_res.get('fired')} "
        f"disagree={ghost_res.get('signals_disagree')} "
        f"a={ghost_res['signal_a']['fires']} b={ghost_res['signal_b']['fires']}"
    )
    if not ghost_ok:
        print("FAILED:CNL-0056-probe1 signals not independent", ghost_res)
        return 1

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe1-disappearing-idea",
                "unit_id": "CNL-0056",
                "dropped_idea_id": DROP_ID,
                "fired": True,
                "independent_recount_agrees": True,
                "duplicate_not_required": True,
                "signals_independent_on_ghost": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNL-0056-probe1 disappearing-idea gap caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
