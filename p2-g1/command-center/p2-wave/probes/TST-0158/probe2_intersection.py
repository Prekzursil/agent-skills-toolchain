#!/usr/bin/env python3
"""Probe 2: independent id-set intersection; last-wins is a FAIL.

Does not trust the merger's collision list. Recomputes set(ids_a) & set(ids_b)
from the two slice documents and requires catalog.by_id last-wins to hide all
31 colliding ids — that silent collapse is the negative control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0158.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0158-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0158" not in json.dumps(doc):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    option_doc = S.option_slice()
    mech_doc = S.mech_slice_pre_reprefix()
    live_ids = S.independent_intersection(option_doc, mech_doc)
    expected = list(S.EXPECTED_COLLISION_IDS)
    if live_ids != expected:
        return fail(f"intersection {live_ids} != seed {expected}")
    if len(live_ids) != 31:
        return fail(f"intersection count {len(live_ids)} != 31")

    last_wins = S.last_wins_via_catalog(option_doc, mech_doc)
    if last_wins.get("silently_took_last_wins") is not True:
        return fail("last-wins control did not hide the 31 collisions")
    if last_wins.get("hidden_collision_count") != 31:
        return fail(f"last-wins hidden count {last_wins.get('hidden_collision_count')}")
    if last_wins.get("catalog_by_id_count") != last_wins.get("union_count"):
        return fail("catalog.by_id did not collapse to the union size")
    # last-wins produced a catalog; that is the FAIL the unit names.
    if last_wins.get("refused") is not False:
        return fail("last-wins unexpectedly refused")

    rec_ids = list((doc.get("independent_intersection") or {}).get("ids") or [])
    if rec_ids != live_ids:
        return fail("artifact independent_intersection.ids != live set-intersection")
    rec_lw = doc.get("last_wins_control") or {}
    if rec_lw.get("silently_took_last_wins") is not True:
        return fail("artifact last_wins_control did not mark last-wins as FAIL")
    rec_count = (doc.get("independent_intersection") or {}).get("count")
    if rec_count != 31:
        return fail(f"artifact intersection count {rec_count}")

    tests = doc.get("tests") or {}
    if (tests.get("last_wins_is_fail") or {}).get("pass") is not True:
        return fail("artifact last_wins_is_fail test not pass")
    if (tests.get("regression_seed_31_way_mnn") or {}).get("pass") is not True:
        return fail("artifact 31-way seed test not pass")

    out = {
        "probe": "probe2-intersection",
        "unit_id": "TST-0158",
        "intersection_count": len(live_ids),
        "intersection_ids": live_ids,
        "last_wins_count": last_wins.get("last_wins_count"),
        "union_count": last_wins.get("union_count"),
        "catalog_by_id_count": last_wins.get("catalog_by_id_count"),
        "last_wins_hid_collisions": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"intersection={len(live_ids)} last_wins_count={last_wins.get('last_wins_count')} "
        f"union={last_wins.get('union_count')} last-wins=FAIL"
    )
    print("SUCCESS:TST-0158-probe2 independent intersection last-wins control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
