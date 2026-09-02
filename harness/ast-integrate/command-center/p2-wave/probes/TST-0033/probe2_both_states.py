#!/usr/bin/env python3
"""Probe 2: both-states control + one negative per contract rule.

Same loader, two inputs: conforming accepted; planted unknown-key rejected.
Mutation: drop additionalProperties=false and the unknown-key case goes green.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import suite as S  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0033.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0033-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0033":
        print("FAILED:TST-0033-probe2 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:TST-0033" not in text:
        print("FAILED:TST-0033-probe2 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0033-probe2 self-declared", st)
        return 1

    report = S.run_suite()
    tests = report["tests"]
    failed = [t["id"] for t in tests if t["verdict"] != "PASS"]
    control = report["controls"]["both_states"]
    mutation = report["controls"]["mutation"]
    payload = {
        "probe": "probe2-both-states-per-rule",
        "unit_id": "TST-0033",
        "suite_ok": report["ok"],
        "n_tests": len(tests),
        "failed": failed,
        "both_states_holds": control["holds"],
        "unknown_field_named": control["unknown_field_named"],
        "mutation_holds": mutation["holds"],
        "pass": bool(
            report["ok"] and control["holds"] and mutation["holds"] and not failed
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    if failed:
        print("FAILED:TST-0033-probe2 per-rule negatives failed", failed)
        return 1
    if not control["holds"]:
        print("FAILED:TST-0033-probe2 both-states control did not hold")
        return 1
    if not mutation["holds"]:
        print("FAILED:TST-0033-probe2 mutation control did not hold")
        return 1
    art_ctrl = (doc.get("controls") or {}).get("both_states") or {}
    if art_ctrl.get("holds") is not True:
        print("FAILED:TST-0033-probe2 receipt did not record both-states holds=true")
        return 1
    print(
        f"n_tests={len(tests)} both_states=True mutation=True "
        f"unknown_named={control['unknown_field_named']}"
    )
    print("SUCCESS:TST-0033-probe2 both-states and per-rule negatives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
