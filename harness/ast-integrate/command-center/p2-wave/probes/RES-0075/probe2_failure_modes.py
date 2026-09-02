#!/usr/bin/env python3
"""Probe 2: >=4 cited failure modes at the same evidence bar as the rules.

Known-broken fixture: a headline number with empty baseline must be E3
and REFUTED. Independent of probe1's in-memory mutation (different file).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    SENTINEL,
    can_promote,
    failure_mode_ok,
    required_fields_ok,
)
import record as R  # noqa: E402

ART = REPO / "command-center/research/RES-0075.json"
FIXTURE = HERE / "fixtures" / "headline_only.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0075-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL not in json.dumps(doc):
        return fail("sentinel-absent")
    modes = doc.get("failure_modes") or []
    if not isinstance(modes, list) or len(modes) < 4:
        return fail(f"need >=4 failure modes, got {len(modes) if isinstance(modes, list) else 0}")

    ok_ids = []
    for row in modes:
        missing = required_fields_ok(row)
        if missing:
            return fail(f"{row.get('id')} missing {missing}")
        if not failure_mode_ok(row):
            return fail(
                f"{row.get('id')} fails citation/effect/baseline bar "
                f"tier={row.get('evidence_tier')} effect={row.get('effect_size')!r}"
            )
        ok_ids.append(row["id"])

    derived_ok = [r["id"] for r in R.FAILURE_MODES if failure_mode_ok(r)]
    if set(ok_ids) != set(derived_ok):
        return fail(f"failure-mode set drifted live={ok_ids} derived={derived_ok}")

    if not FIXTURE.is_file():
        return fail("headline_only fixture missing")
    planted = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if can_promote(planted):
        return fail("known-broken headline_only still promotable")
    if planted.get("evidence_tier") != "E3":
        return fail(f"known-broken tier {planted.get('evidence_tier')!r} expected E3")
    if str(planted.get("verdict") or "").upper() != "REFUTED":
        return fail(f"known-broken verdict {planted.get('verdict')!r} expected REFUTED")

    emp_ids = set((doc.get("rules_split") or {}).get("empirically_supported_ids") or [])
    if planted.get("id") in emp_ids:
        return fail("headline_only id leaked into empirically_supported")

    # Live E3/REFUTED rules must not sit in the empirical list.
    for row in doc.get("claims") or []:
        if row.get("evidence_tier") in {"E3", "E4"} and row.get("id") in emp_ids:
            return fail(f"E3/E4 claim {row.get('id')} promoted")
        if str(row.get("verdict") or "").upper() == "REFUTED" and row.get("id") in emp_ids:
            return fail(f"REFUTED claim {row.get('id')} promoted")

    print(f"failure_modes={ok_ids} n={len(ok_ids)}")
    print(
        "known_broken "
        f"promotable={can_promote(planted)} "
        f"tier={planted.get('evidence_tier')} "
        f"verdict={planted.get('verdict')}"
    )
    print("SUCCESS:RES-0075-probe2 failure-modes + e3-demotion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
