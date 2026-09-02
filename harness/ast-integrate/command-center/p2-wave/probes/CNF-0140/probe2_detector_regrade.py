#!/usr/bin/env python3
"""Probe 2: empty-records 100% gaps, empty-pop not 100% coverage, regrade re-injection."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import controls as C  # noqa: E402
import overclaim as O  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0140.json"


def main() -> int:
    empty = C.empty_records_detector()
    vacuous = C.empty_population_detector()
    regrade = C.severity_coupling()
    checks = [
        ("empty_records_full_gaps", empty.get("full_gaps")),
        ("empty_records_not_100_coverage", empty.get("not_full_coverage")),
        ("empty_records_ok", empty.get("ok")),
        ("empty_population_refuses_100", vacuous.get("ok")),
        ("regrade_appeared", regrade.get("appeared")),
        ("regrade_flag", regrade.get("regraded")),
        ("regrade_ok", regrade.get("ok")),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:CNF-0140-probe2 {name}")
            print(f"  empty_coverage={empty.get('coverage_rate')} n={empty.get('n')}")
            print(f"  vacuous_coverage={vacuous.get('coverage_rate')}")
            print(f"  regrade_ids={regrade.get('after_ids')}")
            return 1
    print(
        "empty_n={0} empty_gap_rate={1} regrade {2}->{3}".format(
            empty.get("n"),
            empty.get("gap_rate"),
            regrade.get("before_n"),
            regrade.get("after_n"),
        )
    )

    if not ART.is_file():
        print("FAILED:CNF-0140-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:CNF-0140" not in text:
        print("FAILED:CNF-0140-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0140-probe2 self-declared {doc.get('state')}")
        return 1
    ok, why = O.check_overclaim(doc)
    print(f"artifact_overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:CNF-0140-probe2 overclaim on live artifact")
        return 1

    mutant = copy.deepcopy(doc)
    mutant["verdict"] = "CONFIRMED"
    mutant.setdefault("census", {})["registry_present"] = False
    mutant.setdefault("counts", {})["gap_count"] = 0
    mutant.setdefault("counts", {})["registry_p0_p1_count"] = 0
    mutant.setdefault("counts", {})["ledger_row_count"] = 0
    mutant.setdefault("census", {})["ledger"] = []
    mutant.setdefault("counts", {})["coverage_rate"] = 1.0
    mok, mwhy = O.check_overclaim(mutant)
    print(f"mutant_vacuous_confirmed_ok={mok} {mwhy}")
    if mok:
        print("FAILED:CNF-0140-probe2 vacuous CONFIRMED mutant was accepted")
        return 1

    live = doc.get("census") or {}
    if live.get("registry_present") is True:
        # Live registry exists: CONFIRMED is allowed only with zero gaps.
        if doc.get("verdict") == "CONFIRMED" and int((doc.get("counts") or {}).get("gap_count") or 0) != 0:
            print("FAILED:CNF-0140-probe2 live CONFIRMED with gaps")
            return 1
    else:
        if doc.get("verdict") == "CONFIRMED":
            print("FAILED:CNF-0140-probe2 live CONFIRMED with registry absent")
            return 1
        if (doc.get("counts") or {}).get("coverage_rate") == 1.0:
            print("FAILED:CNF-0140-probe2 live 100% coverage with registry absent")
            return 1

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "T1-known-present",
        "T2-empty-records-gaps",
        "T3-cross-registry",
        "T4-severity-coupling",
    ):
        row = tests.get(tid)
        if not row or row.get("result") != "PASS":
            print(f"FAILED:CNF-0140-probe2 artifact test {tid} not PASS")
            return 1

    print("SUCCESS:CNF-0140-probe2 empty-records regrade live-honesty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
