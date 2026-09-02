#!/usr/bin/env python3
"""Probe 2: detector control — planted coercion fires; quoted twin is silent.

Mechanically independent of probe 1's live-corpus pass: this probe only loads
the planted / quoted fixtures and requires both states.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0059.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0059-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0059" not in json.dumps(doc):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    planted = E.planted_control()
    quoted = E.quoted_control()
    if not planted["fired"]:
        return fail(f"planted detector did not fire checks={planted['required_checks']}")
    if not quoted["silent"]:
        return fail(f"quoted twin not silent hazards={quoted['hazards']}")

    rec = doc.get("tests") or []
    rec_t2 = next(
        (
            t
            for t in rec
            if isinstance(t, dict)
            and t.get("id")
            in {"test_probe_detects_a_planted_coercion", "t2"}
        ),
        None,
    )
    if not rec_t2 or rec_t2.get("result") != "PASS":
        return fail("artifact test_probe_detects_a_planted_coercion is not PASS")

    controls = doc.get("negative_controls") or []
    if len(controls) < 2:
        return fail("artifact missing both-states negative_controls")
    fired = [c for c in controls if c.get("fired_on_bad_state") is True]
    silent = [c for c in controls if c.get("silent_on_good_state") is True]
    if not fired or not silent:
        return fail("artifact controls do not record both states")

    out = {
        "probe": "probe2-planted-coercion",
        "unit_id": "TST-0059",
        "planted_fired": True,
        "quoted_silent": True,
        "planted_hazard_count": planted["hazard_count"],
        "required_checks": planted["required_checks"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"planted fired={planted['fired']} hazards={planted['hazard_count']} "
        f"quoted_silent={quoted['silent']}"
    )
    print("SUCCESS:TST-0059-probe2 planted coercion detector both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
