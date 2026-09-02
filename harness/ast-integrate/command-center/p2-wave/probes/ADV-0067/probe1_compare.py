#!/usr/bin/env python3
"""Probe 1: minimum-substance package score next to a genuine package score."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_common as C  # noqa: E402

ART = C.ART


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0067-probe1 {msg}")
    return 1


def main() -> int:
    live = C.compare_packages()
    summary = {
        "probe": live["probe"],
        "unit_id": live["unit_id"],
        "genuine_total": live["genuine"]["total"],
        "gamed_total": live["gamed"]["total"],
        "empty_total": live["empty"]["total"],
        "cheap_terms": live["cheap_terms_gamed_beats_genuine"],
        "named_inversion_term": live["named_inversion_term"],
        "gamed_matches_or_beats_genuine": live["gamed_matches_or_beats_genuine"],
        "substance_gamed_weaker": live["substance_gamed_weaker"],
        "production_module_present": live["production_module_present"],
        "control_genuine_not_lower": live["control_genuine_not_lower"],
        "control_empty_lowest": live["control_empty_lowest"],
        "control_no_tests_lower": live["control_no_tests_lower"],
        "control_popularity_invariant": live["control_popularity_invariant"],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))

    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if C.CATALOG_SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "ADV-0067":
        return fail(f"unit_id={doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    rec = doc.get("probe1_comparison") or {}
    if abs(float(rec.get("genuine_total", -1)) - live["genuine"]["total"]) > 1e-6:
        return fail("artifact genuine_total drifted from live score")
    if abs(float(rec.get("gamed_total", -1)) - live["gamed"]["total"]) > 1e-6:
        return fail("artifact gamed_total drifted from live score")
    if rec.get("named_inversion_term") != live["named_inversion_term"]:
        return fail("artifact inversion term drifted")
    if not live["substance_gamed_weaker"]:
        return fail("gamed substance was not weaker; fixtures are not an attack pair")
    if not live["control_empty_lowest"]["pass"]:
        return fail("empty package was not lowest")
    if not live["control_no_tests_lower"]["pass"]:
        return fail("no-tests control failed")
    if not live["control_popularity_invariant"]["pass"]:
        return fail("popularity changed the score")
    if not live["genuine"]["rederivable"] or not live["gamed"]["rederivable"]:
        return fail("score not rederivable from components")

    print(
        f"genuine={live['genuine']['total']} gamed={live['gamed']['total']} "
        f"empty={live['empty']['total']} inversion={live['named_inversion_term']}"
    )
    print("SUCCESS:ADV-0067-probe1 min-substance versus genuine")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
