#!/usr/bin/env python3
"""Probe 1: both-states on the corpus builder.

Feed one case every source (and the fusion) can run, and one case no source
can run. The builder must accept exactly the first and reject the second.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402

RAW = HERE / "probe1-both-states.raw.json"


def main() -> int:
    result = C.both_states()
    RAW.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "accepted_ids={0} accepted_exactly_positive={1} "
        "rejected_negative={2} n_kept={3}".format(
            result["accepted_ids"],
            result["accepted_exactly_positive"],
            result["rejected_negative"],
            result["n_kept"],
        )
    )
    if not result["accepted_exactly_positive"] or not result["rejected_negative"]:
        print("FAILED:WFA-0129-probe1 both-states did not discriminate")
        return 1
    print(
        "NEGATIVE-CONTROL: case-no-source required_capabilities="
        "[capability-no-actor-holds] kept=False "
        "(corpus.filter_cases rejects it; fusion and sources lack the cap)"
    )
    print("SUCCESS:WFA-0129-probe1 both-states accept-all reject-none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
