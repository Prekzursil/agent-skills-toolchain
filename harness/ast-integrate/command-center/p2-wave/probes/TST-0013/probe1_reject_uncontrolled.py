#!/usr/bin/env python3
"""Probe 1: harness REJECTS silent-in-both and fires-in-both checks."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HARNESS = REPO / "command-center" / "harness"
sys.path.insert(0, str(HARNESS))

from test_both_states import (  # noqa: E402
    test_harness_rejects_a_check_silent_in_both_states,
    test_harness_rejects_a_check_that_fires_in_both_states,
    test_harness_rejects_inverted_polarity,
)


def main() -> int:
    silent = test_harness_rejects_a_check_silent_in_both_states()
    both = test_harness_rejects_a_check_that_fires_in_both_states()
    inverted = test_harness_rejects_inverted_polarity()
    print(f"silent_in_both verdict={silent.verdict} reason={silent.rejection_reason}")
    print(f"fires_in_both verdict={both.verdict} reason={both.rejection_reason}")
    print(f"polarity verdict={inverted.verdict} reason={inverted.rejection_reason}")
    if not (
        silent.verdict == "REJECTED"
        and both.verdict == "REJECTED"
        and inverted.verdict == "REJECTED"
    ):
        print("FAILED:TST-0013-probe1 expected three REJECTED records")
        return 1
    print(
        "SUCCESS:TST-0013-probe1 harness rejects silent-in-both, "
        "fires-in-both, and inverted polarity"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
