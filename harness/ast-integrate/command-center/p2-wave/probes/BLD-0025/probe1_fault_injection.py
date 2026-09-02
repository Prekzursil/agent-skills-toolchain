#!/usr/bin/env python3
"""Probe 1: fail-once-then-succeed must be reported, not swallowed.

Re-runs the injection live. Also checks the register recorded the same class.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from instrument import classify, run_through_wrapper  # noqa: E402
from run_audit import findings_from_register  # noqa: E402
from wrappers import FailOnceService, retry_backoff  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0025.json"


def main() -> int:
    svc = FailOnceService()

    def wrap(fn):
        return retry_backoff(fn, max_attempts=3)

    log, result, exc = run_through_wrapper(
        "probe1.fail_once", wrap, svc, wrapper_name="retry_backoff"
    )
    cls = classify(log)
    print(
        json.dumps(
            {
                "classification": cls,
                "success_attempt": log.success_attempt,
                "always_fails_once": log.always_fails_once,
                "first_attempt_error": log.first_attempt_error,
                "distribution": log.distribution(),
                "wrapper_exc": None if exc is None else type(exc).__name__,
                "wrapper_ok": result is not None,
                "calls": svc.calls,
            },
            sort_keys=True,
        )
    )
    if cls != "MASKED_DEFECT":
        print(f"FAILED:BLD-0025-probe1 expected MASKED_DEFECT got {cls}")
        return 1
    if not log.always_fails_once or log.success_attempt != 2:
        print("FAILED:BLD-0025-probe1 expected fail-then-succeed on attempt 2")
        return 1
    if "DeterministicConnectError" not in log.first_attempt_error:
        print("FAILED:BLD-0025-probe1 first-attempt error missing verbatim type")
        return 1
    if exc is not None or result is None:
        print("FAILED:BLD-0025-probe1 wrapper did not swallow into a success")
        return 1
    if svc.calls != 2:
        print(f"FAILED:BLD-0025-probe1 calls={svc.calls} want 2")
        return 1

    if not ART.is_file():
        print("FAILED:BLD-0025-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:BLD-0025" not in json.dumps(doc):
        print("FAILED:BLD-0025-probe1 sentinel absent")
        return 1
    rows = [f for f in findings_from_register(doc) if f.get("id") == "F-MASK-FAIL-ONCE"]
    if not rows or rows[0].get("classification") != "MASKED_DEFECT":
        print("FAILED:BLD-0025-probe1 register did not report the injected fault")
        return 1
    if rows[0].get("first_attempt_error") != log.first_attempt_error:
        print("FAILED:BLD-0025-probe1 register first-attempt error drifted from live injection")
        return 1
    tests = {t["id"]: t["result"] for t in doc.get("tests") or [] if isinstance(t, dict)}
    if tests.get("fault-injection-fail-once-reported") != "PASS":
        print("FAILED:BLD-0025-probe1 receipt test row not PASS")
        return 1
    print("typed_injection=MASKED_DEFECT swallowed=True attempts=2/2")
    print("SUCCESS:BLD-0025-probe1 fail-once-then-succeed reported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
