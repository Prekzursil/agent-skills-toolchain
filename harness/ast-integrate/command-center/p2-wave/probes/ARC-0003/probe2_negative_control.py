#!/usr/bin/env python3
"""Probe 2: negative control.

A deliberately non-declarative construct (stopping rule requiring runtime
evaluation of a predicate over prior rounds) MUST fail mapping. A purely
declarative sample from the same suite MUST still map (both-states).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mapper as M  # noqa: E402

SAMPLES = Path(__file__).resolve().parent / "samples.json"


def main() -> int:
    doc = json.loads(SAMPLES.read_text(encoding="utf-8"))
    bad = doc["negative_control"]
    good = doc["samples"][0]
    author_bad = M.transcribe_author(bad)
    indep_bad = M.transcribe_independent(bad)
    author_good = M.transcribe_author(good)
    indep_good = M.transcribe_independent(good)
    token = "runtime-stopping-predicate-over-prior-rounds"
    bad_ok = (
        author_bad.get("verdict") == "INEXPRESSIBLE"
        and indep_bad.get("verdict") == "INEXPRESSIBLE"
        and token in str(author_bad.get("first_construct"))
        and token in str(indep_bad.get("first_construct"))
    )
    good_ok = (
        author_good.get("verdict") == "EXPRESSIBLE"
        and indep_good.get("verdict") == "EXPRESSIBLE"
        and author_good.get("sha256") == indep_good.get("sha256")
    )
    # Repair mutant: drop the runtime predicate; mapping must become EXPRESSIBLE.
    repaired = copy.deepcopy(bad)
    repaired["body"]["stopping"] = {"max_rounds": 1, "on_timeout": "halt"}
    author_fix = M.transcribe_author(repaired)
    indep_fix = M.transcribe_independent(repaired)
    fix_ok = (
        author_fix.get("verdict") == "EXPRESSIBLE"
        and indep_fix.get("verdict") == "EXPRESSIBLE"
        and author_fix.get("sha256") == indep_fix.get("sha256")
    )
    print(
        f"negative author={author_bad.get('verdict')} construct={author_bad.get('first_construct')}"
    )
    print(
        f"negative indep={indep_bad.get('verdict')} construct={indep_bad.get('first_construct')}"
    )
    print(
        f"good id={good.get('id')} author={author_good.get('verdict')} indep={indep_good.get('verdict')}"
    )
    print(
        f"repaired author={author_fix.get('verdict')} indep={indep_fix.get('verdict')}"
    )
    print(f"fired_on_bad={bad_ok} silent_on_good={good_ok} repaired_expressible={fix_ok}")
    if not (bad_ok and good_ok and fix_ok):
        print("FAILED:ARC-0003-probe2 negative control did not discriminate")
        return 1
    print("SUCCESS:ARC-0003-probe2 negative control mapping fails as required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
