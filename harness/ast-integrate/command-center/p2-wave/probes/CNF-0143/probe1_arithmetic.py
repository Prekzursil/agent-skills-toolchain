#!/usr/bin/env python3
"""Probe 1: arithmetic control + known-absent control (rate computation).

Mechanically: recomputes both rates from the frozen control frame. A non-empty
BLOCKED set must change the published rate; an empty set must not. A wiring
mutant that uses the same denominator for both rates must be rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import accounting as A  # noqa: E402
import live as L  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0143.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0143/probe1_arithmetic.py"
)


def _row(result: dict, sid: str) -> dict:
    if sid == "OVERALL":
        return result["overall"]
    for row in result["strata"]:
        if row["stratum_id"] == sid:
            return row
    raise SystemExit(f"FAILED:CNF-0143-probe1 missing stratum {sid}")


def main() -> int:
    bundle = A.load_control_set()
    frame = bundle["frame"]
    exp = bundle["expected"]

    nonempty = A.compute_rates(bundle["records_nonempty_blocked"], frame)
    empty = A.compute_rates(bundle["records_empty_blocked"], frame)

    ov = nonempty["overall"]
    if int(ov["n_blocked"]) <= 0:
        print("FAILED:CNF-0143-probe1 nonempty fixture has empty BLOCKED set")
        return 1
    if ov["rate_with_blocked_in_denominator"]["as_string"] != exp["nonempty"]["overall"]["rate_with"]:
        print(
            "FAILED:CNF-0143-probe1 overall rate_with "
            f"{ov['rate_with_blocked_in_denominator']['as_string']} "
            f"!= {exp['nonempty']['overall']['rate_with']}"
        )
        return 1
    if ov["rate_without_blocked"]["as_string"] != exp["nonempty"]["overall"]["rate_without"]:
        print(
            "FAILED:CNF-0143-probe1 overall rate_without "
            f"{ov['rate_without_blocked']['as_string']} "
            f"!= {exp['nonempty']['overall']['rate_without']}"
        )
        return 1
    if not ov["rates_differ"]:
        print("FAILED:CNF-0143-probe1 arithmetic: nonempty BLOCKED rates identical (wiring bug)")
        return 1

    sid_a = exp["stratum_a"]
    sid_b = exp["stratum_b"]
    sid_c = exp["stratum_c"]
    a = _row(nonempty, sid_a)
    b = _row(nonempty, sid_b)
    c = _row(nonempty, sid_c)
    if a["rate_with_blocked_in_denominator"]["as_string"] != "3/5":
        print("FAILED:CNF-0143-probe1 stratum A with")
        return 1
    if a["rate_without_blocked"]["as_string"] != "3/4":
        print("FAILED:CNF-0143-probe1 stratum A without")
        return 1
    if not a["rates_differ"]:
        print("FAILED:CNF-0143-probe1 stratum A must differ")
        return 1
    if b["rate_with_blocked_in_denominator"]["as_string"] != b["rate_without_blocked"]["as_string"]:
        print("FAILED:CNF-0143-probe1 stratum B (empty BLOCKED) must coincide")
        return 1
    if int(b["n_blocked"]) != 0:
        print("FAILED:CNF-0143-probe1 stratum B n_blocked")
        return 1
    if c["rate_with_blocked_in_denominator"]["as_string"] != "1/3":
        print("FAILED:CNF-0143-probe1 stratum C with")
        return 1
    if c["rate_without_blocked"]["as_string"] != "1/2":
        print("FAILED:CNF-0143-probe1 stratum C without")
        return 1

    ev = empty["overall"]
    if int(ev["n_blocked"]) != 0:
        print("FAILED:CNF-0143-probe1 empty-blocked fixture is not empty")
        return 1
    if ev["rate_with_blocked_in_denominator"]["as_string"] != ev["rate_without_blocked"]["as_string"]:
        print("FAILED:CNF-0143-probe1 known-absent: empty BLOCKED rates differ")
        return 1
    if ev["rate_with_blocked_in_denominator"]["as_string"] != exp["empty_blocked"]["overall"]["rate_with"]:
        print("FAILED:CNF-0143-probe1 empty-blocked expected rate")
        return 1

    mutant = A.wiring_bug_clone(nonempty)
    caught = False
    try:
        A.assert_invariants(mutant["strata"], mutant["overall"])
    except A.AccountingError as exc:
        caught = "wiring bug" in str(exc)
        print(f"wiring_mutant_caught={caught} err={exc}")
    if not caught:
        print("FAILED:CNF-0143-probe1 wiring mutant not caught")
        return 1

    live = L.harvest(REPO)
    print(
        f"live_records={live['record_count']} live_blocked={live['blocked_count']} "
        f"cnf_0137={live['cnf_0137_present']}"
    )
    if live["cnf_0137_present"] and live["frame"] is not None and live["records"]:
        live_rates = A.compute_rates(live["records"], live["frame"])
        print("live_overall", live_rates["overall"]["rate_with_blocked_in_denominator"]["as_string"])
    else:
        print("live_rates=vacant (no live frame+records; not claimed as a program pass rate)")

    if not ART.is_file():
        print("FAILED:CNF-0143-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0143-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNF-0143" not in text:
        print("FAILED:CNF-0143-probe1 sentinel absent")
        return 1
    art_ov = (A.artifact_published_rates(doc).get("overall") or {})
    if art_ov.get("rate_with_blocked_in_denominator", {}).get("as_string") != "6/12":
        print("FAILED:CNF-0143-probe1 artifact overall with mismatch")
        return 1
    if art_ov.get("rate_without_blocked", {}).get("as_string") != "6/10":
        print("FAILED:CNF-0143-probe1 artifact overall without mismatch")
        return 1
    if int((A.artifact_excluded_set(doc) or {}).get("count") or 0) != 2:
        print("FAILED:CNF-0143-probe1 excluded_set count")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-arithmetic",
                "unit_id": "CNF-0143",
                "nonempty_blocked": ov["n_blocked"],
                "rate_with": ov["rate_with_blocked_in_denominator"]["as_string"],
                "rate_without": ov["rate_without_blocked"]["as_string"],
                "rates_differ": ov["rates_differ"],
                "empty_blocked_coincide": (
                    ev["rate_with_blocked_in_denominator"]["as_string"]
                    == ev["rate_without_blocked"]["as_string"]
                ),
                "wiring_mutant_caught": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0143-probe1 arithmetic and known-absent controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
