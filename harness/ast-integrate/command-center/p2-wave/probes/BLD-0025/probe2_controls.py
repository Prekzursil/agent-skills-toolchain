#!/usr/bin/env python3
"""Probe 2: 429 is TRANSIENT; zero-retry absent; re-read first-attempt errors.

Independent of probe 1: re-runs 429 and no-retry wrappers, then re-classifies
the register's MASKED_DEFECT first-attempt error as a real defect.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from instrument import classify, is_transient_error, run_through_wrapper  # noqa: E402
from run_audit import (  # noqa: E402
    excluded_from_register,
    findings_from_register,
    review_first_attempt_errors,
)
from wrappers import AlwaysOk, RateLimitedThenOk, no_retry, retry_backoff  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0025.json"


def main() -> int:
    rate = RateLimitedThenOk()

    def wrap(fn):
        return retry_backoff(fn, max_attempts=3)

    log_429, res_429, err_429 = run_through_wrapper(
        "probe2.vendor_429", wrap, rate, wrapper_name="retry_backoff"
    )
    cls_429 = classify(log_429)
    print(
        f"transient_cls={cls_429} status_in_error={'429' in log_429.first_attempt_error} "
        f"retry_after={'Retry-After' in log_429.first_attempt_error} "
        f"success_attempt={log_429.success_attempt}"
    )
    if cls_429 != "TRANSIENT":
        print(f"FAILED:BLD-0025-probe2 expected TRANSIENT got {cls_429}")
        return 1
    if err_429 is not None or res_429 is None:
        print("FAILED:BLD-0025-probe2 429 wrapper did not succeed on retry")
        return 1
    if not is_transient_error(log_429.first_attempt_error):
        print("FAILED:BLD-0025-probe2 missing rate-limit evidence on first error")
        return 1

    zero = AlwaysOk()
    log_z, res_z, err_z = run_through_wrapper(
        "probe2.zero_retry", no_retry, zero, wrapper_name="no_retry"
    )
    cls_z = classify(log_z)
    print(f"zero_cls={cls_z} calls={zero.calls} ok={res_z is not None}")
    if cls_z != "FIRST_ATTEMPT_OK" or zero.calls != 1 or err_z is not None:
        print("FAILED:BLD-0025-probe2 zero-retry control misbehaved")
        return 1

    if not ART.is_file():
        print("FAILED:BLD-0025-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    findings = findings_from_register(doc)
    ids = [f.get("id") for f in findings]
    if "C-ZERO-MEASURE-RUN-CMD" in ids or "C-ZERO-NO-RETRY-WRAPPER" in ids:
        print("FAILED:BLD-0025-probe2 zero-retry control leaked into findings")
        return 1
    trans_rows = [f for f in findings if f.get("id") == "F-TRANSIENT-429"]
    if not trans_rows or trans_rows[0].get("classification") != "TRANSIENT":
        print("FAILED:BLD-0025-probe2 register missing TRANSIENT 429 row")
        return 1
    if trans_rows[0].get("first_attempt_error") != log_429.first_attempt_error:
        print("FAILED:BLD-0025-probe2 429 first-attempt error drifted from live run")
        return 1

    excluded = excluded_from_register(doc)
    if not any(e.get("id") == "C-ZERO-MEASURE-RUN-CMD" for e in excluded):
        print("FAILED:BLD-0025-probe2 excluded zero-retry site missing")
        return 1

    reviewer = review_first_attempt_errors(findings)
    print(
        json.dumps(
            {
                "reviewer_verdict": reviewer.get("verdict"),
                "confirmed": reviewer.get("confirmed_real_defect"),
            },
            sort_keys=True,
        )
    )
    if reviewer.get("verdict") != "PASS" or not reviewer.get("confirmed_real_defect"):
        print("FAILED:BLD-0025-probe2 first-attempt re-read did not confirm a real defect")
        return 1
    confirmed_err = str(reviewer["confirmed_real_defect"]["first_attempt_error"])
    if is_transient_error(confirmed_err):
        print("FAILED:BLD-0025-probe2 confirmed defect was actually a 429")
        return 1

    tests = {t["id"]: t["result"] for t in doc.get("tests") or [] if isinstance(t, dict)}
    if tests.get("control-vendor-429-transient") != "PASS":
        print("FAILED:BLD-0025-probe2 receipt 429 test not PASS")
        return 1
    if tests.get("control-zero-retry-absent") != "PASS":
        print("FAILED:BLD-0025-probe2 receipt zero-retry test not PASS")
        return 1

    print("overclaim_ok=True 429=TRANSIENT zero_retry_absent=True reviewer=PASS")
    print("SUCCESS:BLD-0025-probe2 controls and first-attempt re-read")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
