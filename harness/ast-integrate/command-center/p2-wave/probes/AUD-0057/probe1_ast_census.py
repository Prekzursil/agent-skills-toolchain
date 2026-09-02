#!/usr/bin/env python3
"""Probe 1: independent AST recount of the default-argument census.

Confirms planted DEFAULT_MIN_BYTES is unexercised and planted factor is
exercised, then checks the artifact counts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

UNIT = "AUD-0057"
ART = REPO / "command-center" / "audit" / "AUD-0057-assertion-strength-census.json"
SENTINEL = (
    "SUCCESS:AUD-0057 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT and doc.get("id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")

    live = C.run_census()
    planted = {f"{r['param']}|{r['qualname']}": r for r in live["planted"]}
    hole = planted.get("min_bytes|aud0057_check_payload_floor")
    ctrl = planted.get("factor|aud0057_scale_by_factor")
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
    for key in ("n_defaults", "n_exercised", "n_unexercised", "n_no_test_calls"):
        if rec.get(key) != live[key]:
            return fail(f"artifact {key}={rec.get(key)} live={live[key]}")
        print(f"match {key}={live[key]}")

    rec_hole = None
    for row in rec.get("unexercised") or []:
        if row.get("param") == "min_bytes" and "aud0057_check_payload_floor" in str(
            row.get("function") or ""
        ):
            rec_hole = row
            break
    if rec_hole is None:
        for row in rec.get("planted") or []:
            if row.get("param") == "min_bytes":
                rec_hole = row
                break
    if rec_hole is None:
        return fail("artifact unexercised/planted list missing planted min_bytes")
    if rec_hole.get("anchor") != hole["anchor"]:
        return fail(f"artifact hole anchor {rec_hole.get('anchor')} != {hole['anchor']}")

    if live["n_defaults"] < 2:
        return fail("census found fewer than the two planted defaults")
    print("SUCCESS:AUD-0057-probe1 census recount planted hole and control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
