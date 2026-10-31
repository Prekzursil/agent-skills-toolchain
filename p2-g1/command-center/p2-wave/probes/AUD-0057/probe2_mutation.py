#!/usr/bin/env python3
"""Probe 2: independent reviewer — mutation both-states, not the AST census.

Re-runs the scratch-copy suite. The unexercised default mutation must stay
green; the exercised default mutation must go red. Does not import classify().
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import mutate as M  # noqa: E402

UNIT = "AUD-0057"
ART = REPO / "command-center" / "audit" / "AUD-0057-assertion-strength-census.json"
SENTINEL = (
    "SUCCESS:AUD-0057 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
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

    live = M.run_mutations()
    print(
        f"baseline_green={live['baseline_green']} "
        f"unexercised_still_green={live['unexercised_default_mutated_still_green']} "
        f"exercised_goes_red={live['exercised_default_mutated_goes_red']} "
        f"unexercised_rc={live['unexercised_rc']} exercised_rc={live['exercised_rc']}"
    )
    if live["baseline_green"] is not True:
        return fail("baseline fixture suite is not green")
    if live["unexercised_default_mutated_still_green"] is not True:
        return fail("unexercised default mutation went red — hole is not real")
    if live["exercised_default_mutated_goes_red"] is not True:
        print(live.get("exercised_tail") or "")
        return fail("exercised default mutation stayed green — harness cannot produce red")
    if live["pass"] is not True:
        return fail("mutation both-states did not pass")

    rec = doc.get("mutation") or {}
    if rec.get("unexercised_default_mutated_still_green") is not True:
        return fail("artifact does not record unexercised mutation staying green")
    if rec.get("exercised_default_mutated_goes_red") is not True:
        return fail("artifact does not record exercised mutation going red")
    print("SUCCESS:AUD-0057-probe2 mutation both-states independent of census AST")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
