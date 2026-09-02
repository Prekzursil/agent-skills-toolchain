#!/usr/bin/env python3
"""Probe 1: independent recount of the planted default-argument census.

Walks fixtures/estate only (tools/ is an emit-time snapshot). Confirms
planted DEFAULT_MIN_BYTES is unexercised, planted scale_by_factor.factor
is exercised, then checks receipt estate counts and the unexercised list.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

UNIT = "TST-0339"
ART = REPO / "command-center" / "receipts" / "TST-0339.json"
SENTINEL = "SUCCESS:TST-0339"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT and doc.get("id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")

    live = C.run_census(include_product=False)
    planted = {f"{r['param']}|{r['qualname']}": r for r in live["planted"]}
    hole = planted.get("min_bytes|check_payload_floor")
    ctrl = planted.get("factor|scale_by_factor")
    print(
        f"live n_defaults={live['n_defaults']} exercised={live['n_exercised']} "
        f"unexercised={live['n_unexercised']} no_calls={live['n_no_test_calls']}"
    )
    if hole is None or hole["status"] != "unexercised":
        return fail(f"planted min_bytes not unexercised: {hole}")
    if hole["calls_supplying"] < 1:
        return fail("planted min_bytes has no supplying call sites")
    if hole["calls_omitting"] != 0:
        return fail("planted min_bytes was omitted by a test")
    print(f"planted_hole {hole['anchor']} status={hole['status']} supply={hole['calls_supplying']}")
    if ctrl is None or ctrl["status"] != "exercised":
        return fail(f"planted factor not exercised: {ctrl}")
    if ctrl["calls_omitting"] < 1:
        return fail("planted factor has no omitting call")
    print(f"planted_ctrl {ctrl['anchor']} status={ctrl['status']} omit={ctrl['calls_omitting']}")

    rec = doc.get("census") or {}
    estate = rec.get("estate") if isinstance(rec.get("estate"), dict) else rec
    for key in ("n_defaults", "n_exercised", "n_unexercised", "n_no_test_calls"):
        if estate.get(key) != live[key]:
            return fail(f"receipt estate {key}={estate.get(key)} live={live[key]}")
        print(f"match {key}={live[key]}")

    if rec.get("n_unexercised") != len(rec.get("unexercised") or []):
        return fail("receipt n_unexercised != len(unexercised)")
    missing_anchor = [
        row
        for row in (rec.get("unexercised") or [])
        if not isinstance(row, dict) or ":" not in str(row.get("anchor") or "")
    ]
    if missing_anchor:
        return fail(f"{len(missing_anchor)} unexercised rows lack file:line")

    rec_hole = None
    search_lists = [
        rec.get("unexercised") or [],
        (rec.get("estate") or {}).get("unexercised") or [],
        rec.get("planted") or [],
        (rec.get("estate") or {}).get("planted") or [],
    ]
    for rows in search_lists:
        for row in rows:
            if not isinstance(row, dict):
                continue
            fn = str(row.get("function") or "")
            if row.get("param") == "min_bytes" and (
                fn == "check_payload_floor" or "check_payload_floor" in fn
            ):
                rec_hole = row
                break
            if (
                rec_hole is None
                and row.get("param") == "min_bytes"
                and "fixtures/estate/product.py" in str(row.get("anchor") or "")
            ):
                rec_hole = row
                break
        if rec_hole is not None:
            break
    if rec_hole is None:
        return fail("receipt unexercised list missing planted min_bytes")
    if rec_hole.get("anchor") != hole["anchor"]:
        return fail(f"receipt hole anchor {rec_hole.get('anchor')} != {hole['anchor']}")

    if live["n_defaults"] < 2:
        return fail("census found fewer than the two planted defaults")
    print("SUCCESS:TST-0339-probe1 census recount planted hole and control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
