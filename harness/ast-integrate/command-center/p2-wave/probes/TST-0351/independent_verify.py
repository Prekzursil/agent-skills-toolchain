#!/usr/bin/env python3
"""Mechanically different verifier for TST-0351 evidence probes.

Does not re-run probe1_*.py / probe2_*.py. Imports the control functions
directly and prints a compact line a third party can grep.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from controls import (  # noqa: E402
    test_claim_extraction_recall_against_hand_labelled_sample,
    test_contradiction_planted_failed_run_is_caught,
    test_resolution_attempted_against_ledger_before_unbacked,
    test_use_versus_mention_describing_document_is_silent,
)


def recall() -> int:
    a = test_claim_extraction_recall_against_hand_labelled_sample()
    b = test_use_versus_mention_describing_document_is_silent()
    print(
        int(a["pass"]),
        a["recalled"],
        a["labelled_use"],
        int(b["pass"]),
        b["use_count"],
        b["mention_count"],
    )
    return 0 if a["pass"] and b["pass"] else 1


def resolve() -> int:
    a = test_resolution_attempted_against_ledger_before_unbacked()
    b = test_contradiction_planted_failed_run_is_caught()
    both = a.get("both_states") or {}
    print(
        int(a["pass"]),
        int(bool(both.get("ledger_read_resolves"))),
        int(bool(both.get("unread_ledger_is_unbacked"))),
        a.get("live_run_id"),
        int(b["pass"]),
        b.get("run_id"),
        b.get("first_class"),
        b.get("reason"),
    )
    return 0 if a["pass"] and b["pass"] else 1


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"recall", "resolve"}:
        print("usage: independent_verify.py recall|resolve", file=sys.stderr)
        return 2
    return recall() if sys.argv[1] == "recall" else resolve()


if __name__ == "__main__":
    raise SystemExit(main())
