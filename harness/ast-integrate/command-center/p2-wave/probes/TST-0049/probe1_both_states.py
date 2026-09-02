#!/usr/bin/env python3
"""Probe 1: both-states control for the compatibility-matrix conformance suite."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import suite as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0049.json"
CONTRACT = REPO / "command-center/phase4/contracts/ARC-0095.json"
SENTINEL = "SUCCESS:TST-0049"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0049-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 400:
        return fail("receipt missing or tiny")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("catalog sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0049":
        return fail(f"unit_id {doc.get('unit_id')!r}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    bat = S.run_fixture_battery()
    if not bat["ok"]:
        print(json.dumps(bat["mismatches"][:4], indent=2)[:3000])
        return fail("fixture battery disagreement")

    by_id = {r["row_id"]: r for r in bat["rows"]}
    good = by_id["conforming-mixed"]
    bad = by_id["supported-without-evidence"]
    if good["candidate_verdict"] != "PASS" or good["oracle_verdict"] != "PASS":
        return fail("conforming fixture did not PASS")
    if bad["candidate_verdict"] != "FAIL" or bad["oracle_verdict"] != "FAIL":
        return fail("planted non-conforming fixture did not FAIL")
    if not bad["naive_would_pass_defect"]:
        return fail("naive checker also failed the planted defect; both-states is silent")

    live = S.evaluate(json.loads(CONTRACT.read_text(encoding="utf-8")))
    stored = doc.get("live_audit") or {}
    if stored.get("asserted_without_evidence") != live["counts"]["asserted_without_evidence"]:
        return fail("live asserted_without_evidence drifted vs receipt")
    if stored.get("untested") != live["counts"]["untested"]:
        return fail("live untested drifted vs receipt")
    table = doc.get("comparison_table") or []
    if len(table) < 10:
        return fail(f"comparison_table too short ({len(table)})")

    out = {
        "probe": "probe1-both-states",
        "unit_id": "TST-0049",
        "pass": True,
        "conforming": good["candidate_verdict"],
        "planted_defect": bad["candidate_verdict"],
        "naive_would_pass_defect": True,
        "live_untested": live["counts"]["untested"],
        "live_asserted_without_evidence": live["counts"]["asserted_without_evidence"],
        "live_blank": live["counts"]["blank"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"conforming={good['candidate_verdict']} planted={bad['candidate_verdict']} "
        f"naive_green_on_defect={bad['naive_would_pass_defect']} "
        f"untested={live['counts']['untested']} asserted={live['counts']['asserted_without_evidence']}"
    )
    print("SUCCESS:TST-0049-probe1 both-states control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
