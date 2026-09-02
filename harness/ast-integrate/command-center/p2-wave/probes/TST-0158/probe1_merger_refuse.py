#!/usr/bin/env python3
"""Probe 1: live merger CLI — refuse + full collision list; disjoint merge clean."""
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
    print(f"FAILED:TST-0158-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(doc)
    if "SUCCESS:TST-0158" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = S.live_experiment()
    if not live.get("pass"):
        return fail(
            "live experiment did not pass "
            f"refuse_ok={live.get('refuse_ok')} disjoint_ok={live.get('disjoint_ok')} "
            f"signals_agree={live.get('signals_agree')} "
            f"last_wins_is_fail={live.get('last_wins_is_fail')}"
        )
    collision = live["collision_run"]
    if collision["exit_code"] != 2:
        return fail(f"merger exit {collision['exit_code']} expected 2")
    if collision.get("wrote_merged_catalog") is not False:
        return fail("collision merge wrote a catalog (last-wins shape)")
    ids = list(collision.get("collision_ids") or [])
    expected = list(S.EXPECTED_COLLISION_IDS)
    if ids != expected:
        return fail(f"collision list {ids} != seed {expected}")
    if len(ids) != 31:
        return fail(f"collision count {len(ids)} != 31")
    if collision.get("order_independent") is not True:
        return fail("collision list depends on slice order")

    disjoint = live["disjoint_run"]
    if disjoint["exit_code"] != 0:
        return fail(f"disjoint merge exit {disjoint['exit_code']}")
    if list(disjoint.get("ids") or []) != [
        "TST-A-0001",
        "TST-A-0002",
        "TST-B-0001",
        "TST-B-0002",
    ]:
        return fail(f"disjoint ids {disjoint.get('ids')}")
    if disjoint.get("wrote_merged_catalog") is not True:
        return fail("disjoint merge did not write")

    rec_ids = list((doc.get("merger_signal") or {}).get("collision_ids") or [])
    if rec_ids != ids:
        return fail("artifact merger_signal.collision_ids != live CLI list")
    rec_exit = (doc.get("merger_signal") or {}).get("exit_code")
    if rec_exit != 2:
        return fail(f"artifact merger exit {rec_exit}")
    rec_disjoint = (doc.get("tests") or {}).get("disjoint_slices_merge_clean") or {}
    if rec_disjoint.get("pass") is not True:
        return fail("artifact disjoint test not pass")

    out = {
        "probe": "probe1-merger-refuse",
        "unit_id": "TST-0158",
        "merger_exit": collision["exit_code"],
        "collision_count": len(ids),
        "collision_ids": ids,
        "disjoint_exit": disjoint["exit_code"],
        "disjoint_ids": disjoint.get("ids"),
        "wrote_on_collision": collision["wrote_merged_catalog"],
        "order_independent": collision["order_independent"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"merger refused exit={collision['exit_code']} "
        f"collisions={len(ids)} disjoint_exit={disjoint['exit_code']}"
    )
    print("SUCCESS:TST-0158-probe1 merger refuse and disjoint control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
