#!/usr/bin/env python3
"""Probe 1: loud-failure control.

Disable schema_support on the openai local adapter and assert the differential
reports MISMATCH rather than PASS/CONFORMANT. The healthy pair must stay
CONFORMANT (both-states).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import conformance as C  # noqa: E402

RUN = HERE / "runs" / "probe1"


def main() -> int:
    result = C.loud_failure_control(RUN)
    baseline = result["baseline"]["verdict"]
    after = result["after_disable"]["verdict"]
    disabled_state = result["openai_disabled"].get("doc_state")
    print(
        f"baseline={baseline} after_disable={after} "
        f"silent_pass={result['silent_pass']} "
        f"disabled_state={disabled_state} "
        f"anthropic_ok={result['anthropic'].get('predicate_ok')} "
        f"openai_ok={result['openai_ok'].get('predicate_ok')} "
        f"openai_disabled_ok={result['openai_disabled'].get('predicate_ok')}"
    )
    if not result["ok"]:
        print("FAILED:ARC-0043-probe1 loud-failure control did not discriminate")
        return 1
    print("SUCCESS:ARC-0043-probe1 loud-failure reports MISMATCH not PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
