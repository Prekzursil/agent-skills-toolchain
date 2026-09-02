#!/usr/bin/env python3
"""Probe 2 (reviewer): hung unit classified timeout-<n>s; survivors complete and attributed.

Mechanically different from probe 1: this probe re-runs classification + survivor
attribution + the all-healthy negative control, and independently recounts the
write-as-you-go ledger. It does not author the naive-vs-fixed watchdog.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402
from pipeline import timeout_class  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0091.json"
UNIT = "TST-0091"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0091" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    classify = S.test_hung_unit_is_classified_timeout_not_silently_dropped()
    survivors = S.test_survivor_results_are_complete_and_attributed()
    negative = S.negative_control_no_hung()
    expected = timeout_class(S.PER_UNIT_TIMEOUT_S)

    hung_rec = classify.get("hung_record") or {}
    mutant_would_fail = classify["mutant_drop_count"] == S.N - 1
    ok = (
        classify["pass"]
        and survivors["pass"]
        and negative["pass"]
        and hung_rec.get("classification") == expected
        and hung_rec.get("state") == "TIMEOUT"
        and classify["dropped"] is False
        and mutant_would_fail
        and survivors["write_as_you_go"] is True
        and negative["n_timeout"] == 0
        and negative["silent_on_good"] is True
    )
    payload = {
        "probe": "probe2-timeout-attribution",
        "unit_id": UNIT,
        "pass": ok,
        "hung_id": classify["hung_id"],
        "hung_state": hung_rec.get("state"),
        "hung_classification": hung_rec.get("classification"),
        "expected_classification": expected,
        "dropped": classify["dropped"],
        "n_records": classify["n_records"],
        "mutant_drop_count": classify["mutant_drop_count"],
        "n_survivors": survivors["n_survivors"],
        "all_attributed": survivors["all_attributed"],
        "all_durable": survivors["all_durable"],
        "write_as_you_go": survivors["write_as_you_go"],
        "negative_n_timeout": negative["n_timeout"],
        "negative_silent_on_good": negative["silent_on_good"],
        "ledger_ids": classify["ledger_ids"],
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    print(
        f"hung={classify['hung_id']} class={hung_rec.get('classification')} "
        f"dropped={classify['dropped']} survivors={survivors['n_survivors']} "
        f"attributed={survivors['all_attributed']} "
        f"write_as_you_go={survivors['write_as_you_go']} "
        f"neg_timeouts={negative['n_timeout']}"
    )
    if not classify["pass"]:
        return fail("classification test")
    if classify["dropped"]:
        return fail("hung unit silently dropped")
    if hung_rec.get("classification") != expected:
        return fail(f"classification {hung_rec.get('classification')} != {expected}")
    if not survivors["pass"]:
        return fail("survivor attribution")
    if not survivors["write_as_you_go"]:
        return fail("survivors not durable before hung classified")
    if not negative["pass"]:
        return fail("negative control (all-healthy) not silent")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "test_hung_unit_is_classified_timeout_not_silently_dropped",
        "test_survivor_results_are_complete_and_attributed",
    ):
        row = tests.get(tid)
        if not row or row.get("result") != "PASS":
            return fail(f"receipt missing PASS for {tid}")
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or reviewer.get("independent") is not True:
        return fail("receipt reviewer")
    neg = doc.get("negative_controls") or []
    if not any(isinstance(c, dict) and c.get("silent_on_good_state") is True for c in neg):
        return fail("receipt negative control missing")

    print("SUCCESS:TST-0091-probe2 timeout classified; survivors attributed; negative silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
