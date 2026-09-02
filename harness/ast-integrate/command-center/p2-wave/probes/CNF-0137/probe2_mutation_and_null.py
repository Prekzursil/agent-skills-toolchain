#!/usr/bin/env python3
"""Probe 2: novel-subsystem mutation + missing-severity null control.

Both-states: the healthy universe still partitions; the mutated copy must
open a new stratum rather than land in 'other'; a claim with no severity
must raise, not default to low.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from frame import FrameBuildError, build_frame, locate_claim  # noqa: E402
from universe import NOVEL_SUBSYSTEM, load_universe  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0137-probe2 {msg}")
    return 1


def main() -> int:
    uni = load_universe()
    vendors = uni["catalog_vendors"]
    try:
        baseline = build_frame(uni["claims"], vendors)
    except FrameBuildError as exc:
        return fail(f"baseline: {exc}")
    base_keys = set(baseline.strata)

    mutated = copy.deepcopy(uni["claims"])
    planted_id = "C-CNF0137-NOVEL-SUBSYSTEM"
    mutated.append(
        {
            "id": planted_id,
            "severity": "P2",
            "subsystem": NOVEL_SUBSYSTEM,
            "author_vendor": "anthropic",
            "claim_type": "existence",
            "text": "planted novel subsystem; must not collapse into 'other'",
        }
    )
    try:
        mut_frame = build_frame(mutated, vendors)
    except FrameBuildError as exc:
        return fail(f"mutation-build: {exc}")
    try:
        mut_key, _ = locate_claim(mut_frame, planted_id)
    except FrameBuildError as exc:
        return fail(f"mutation-locate: {exc}")
    if mut_key[1] != NOVEL_SUBSYSTEM:
        return fail(f"novel claim subsystem={mut_key[1]} expected {NOVEL_SUBSYSTEM}")
    if mut_key[1].lower() in {"other", "unknown", "misc", "unspecified"}:
        return fail("novel subsystem was bucketed into a catch-all")
    if mut_key in base_keys:
        return fail("novel subsystem reused an existing stratum key")
    if mut_key not in mut_frame.strata:
        return fail("novel stratum missing from mutated frame")
    if planted_id in [cid for members in baseline.strata.values() for cid in members]:
        return fail("planted id leaked into baseline")

    null_rows = copy.deepcopy(uni["claims"])
    null_rows.append(
        {
            "id": "C-CNF0137-MISSING-SEVERITY",
            "subsystem": "schema",
            "author_vendor": "anthropic",
            "claim_type": "existence",
            "text": "severity omitted on purpose",
        }
    )
    try:
        build_frame(null_rows, vendors)
    except FrameBuildError as exc:
        err = str(exc)
        if "severity" not in err.lower():
            return fail(f"null-field error did not name severity: {exc}")
        if "default to low" not in err.lower() and "refusing to default" not in err.lower():
            return fail(f"null-field error was not the loud default-refusal: {exc}")
        null_fired = True
        null_error = err
    else:
        return fail("missing severity was accepted; would have defaulted the denominator")

    payload = {
        "pass": True,
        "probe": "probe2-mutation-and-null",
        "baseline_n": baseline.proof["registry_n"],
        "baseline_strata": len(base_keys),
        "mutated_n": mut_frame.proof["registry_n"],
        "mutated_strata": len(mut_frame.strata),
        "new_stratum": "|".join(mut_key),
        "novel_subsystem": NOVEL_SUBSYSTEM,
        "not_bucketed_other": True,
        "null_severity_raised": null_fired,
        "null_error": null_error,
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        f"baseline_n={baseline.proof['registry_n']} "
        f"mutated_strata={len(mut_frame.strata)} "
        f"new={('|'.join(mut_key))} null_fired={null_fired}"
    )
    print("SUCCESS:CNF-0137-probe2 mutation-new-stratum and null-severity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
