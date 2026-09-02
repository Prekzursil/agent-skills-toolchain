#!/usr/bin/env python3
"""Probe 2: one negative per contract rule, plus both-states on a live ARC-0005 receipt."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import suite  # noqa: E402

def main() -> int:
    result = suite.probe2_body()
    both = result["both_states_control"]
    print(
        f"rules={result['rule_count']} pass={result['rules_pass']} "
        f"fired_on_bad={both['fired_on_bad']} silent_on_good={both['silent_on_good']} "
        f"live={both['good_fixture']}"
    )
    print("SUCCESS:TST-0039-probe2 negatives and both-states")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"FAILED:TST-0039-probe2 {type(exc).__name__}: {exc}")
        raise SystemExit(1)
