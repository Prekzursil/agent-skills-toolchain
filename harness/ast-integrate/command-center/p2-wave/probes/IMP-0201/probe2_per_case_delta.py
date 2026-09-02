#!/usr/bin/env python3
"""Named probe 2: same-corpus delta is recomputed from per-case rows, not summary.

Two independent readings:
  1. compare_to_baseline() on a baseline whose stored summary.mean_score is a lie.
  2. delta_from_rows() which has no summary parameter at all.

They must agree with each other and with the arithmetic on the fixture rows.
A summary-only baseline (rows stripped) must be refused with SUMMARY_ONLY_REFUSED.
If the stored summaries were the substrate, mean_delta would be 1 - 999 = -998.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.evals.baseline import (  # noqa: E402
    REASON_SUMMARY_ONLY,
    compare_to_baseline,
    delta_from_rows,
    load_json,
)
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0201.json"
FIX = HERE / "fixtures"


def _fail(msg: str, extra=None) -> int:
    print(f"FAILED:IMP-0201-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:2000])
    return 1


def independent_mean_from_fixture_rows() -> tuple[int, int, float, dict[str, int]]:
    """Arithmetic that never opens the summary field."""
    by_id = {r["case_id"]: r["score"] for r in S.ROWS_CERTIFIED}
    deltas = {}
    num = 0
    for r in S.ROWS_LATER:
        d = r["score"] - by_id[r["case_id"]]
        deltas[r["case_id"]] = d
        num += d
    n = len(deltas)
    return num, n, num / n, deltas


def main() -> int:
    S.write_fixtures(FIX)
    baseline = load_json(FIX / "baseline-certified.json")
    same = load_json(FIX / "run-same-corpus.json")
    summary_only = load_json(FIX / "baseline-summary-only.json")

    if baseline.get("summary", {}).get("mean_score") != 999:
        return _fail("lying baseline summary was not 999; probe cannot discriminate")
    if same.get("summary", {}).get("mean_score") != 1:
        return _fail("lying run summary was not 1; probe cannot discriminate")
    if summary_only.get("per_case_rows"):
        return _fail("summary-only fixture still has rows")

    via_compare = compare_to_baseline(same, baseline)
    via_rows = delta_from_rows(same["per_case_rows"], baseline["per_case_rows"])
    num, den, mean, expected = independent_mean_from_fixture_rows()
    summary_delta_if_trusted = 1 - 999

    refused = compare_to_baseline(same, summary_only)

    report = {
        "probe": "probe2-per-case-delta",
        "unit_id": "IMP-0201",
        "via_compare_ok": bool(via_compare.get("ok")),
        "via_compare_mean": via_compare.get("mean_delta"),
        "via_rows_mean": via_rows.get("mean_delta"),
        "independent_mean": mean,
        "numerator": num,
        "denominator": den,
        "summary_delta_if_trusted": summary_delta_if_trusted,
        "summary_consulted_compare": via_compare.get("summary_consulted"),
        "summary_consulted_rows": via_rows.get("summary_consulted"),
        "summary_only_reason": refused.get("reason"),
        "pass": False,
    }

    if not via_compare.get("ok"):
        return _fail("same-corpus compare refused", via_compare)
    if not via_rows.get("ok"):
        return _fail("delta_from_rows refused", via_rows)
    if via_compare.get("summary_consulted") is not False:
        return _fail("compare consulted summary", via_compare)
    if via_rows.get("summary_consulted") is not False:
        return _fail("delta_from_rows consulted summary", via_rows)
    if via_compare.get("mean_delta_numerator") != num:
        return _fail(
            f"compare numerator {via_compare.get('mean_delta_numerator')} want {num}",
            via_compare,
        )
    if via_rows.get("mean_delta_numerator") != num:
        return _fail("delta_from_rows numerator mismatch", via_rows)
    if via_compare.get("mean_delta") != mean or via_rows.get("mean_delta") != mean:
        return _fail("mean_delta disagreement across the two instruments", report)
    if via_compare.get("mean_delta") == summary_delta_if_trusted:
        return _fail("mean_delta equals summary-only arithmetic; rows were ignored")
    if abs(via_compare.get("mean_delta") - summary_delta_if_trusted) < 1:
        return _fail("mean_delta too close to summary lie to prove rows were used")

    got_deltas = {
        row["case_id"]: row["delta"] for row in via_compare.get("per_case_deltas") or []
    }
    if got_deltas != expected:
        return _fail("per-case deltas do not match row arithmetic", got_deltas)
    row_deltas = {
        row["case_id"]: row["delta"] for row in via_rows.get("per_case_deltas") or []
    }
    if row_deltas != expected:
        return _fail("delta_from_rows per-case deltas drifted", row_deltas)

    if refused.get("ok") or not refused.get("refused"):
        return _fail("summary-only baseline was not refused", refused)
    if refused.get("reason") != REASON_SUMMARY_ONLY:
        return _fail(
            f"summary-only reason {refused.get('reason')!r} want {REASON_SUMMARY_ONLY}",
            refused,
        )

    if not ART.is_file() or ART.stat().st_size < 200:
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0201" not in text:
        return _fail("sentinel absent")
    if "per-case" not in text.lower() and "per_case" not in text:
        return _fail("receipt does not cite per-case rows")
    if REASON_SUMMARY_ONLY not in text:
        return _fail("receipt does not name SUMMARY_ONLY_REFUSED")

    report["pass"] = True
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        f"row_mean={mean} summary_if_trusted={summary_delta_if_trusted} "
        f"summary_only_refused={REASON_SUMMARY_ONLY}"
    )
    print("SUCCESS:IMP-0201-probe2 delta from per-case rows, summary ignored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
