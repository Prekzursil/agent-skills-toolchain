#!/usr/bin/env python3
"""Probe 1: contradictory pair flagged; compatible look-alike not flagged.

Both-states: (1) planted polarity/exclusive conflicts fire; (2) a pair whose
prose names unanimity/forbid/egress/air-gap but whose trees agree stays silent.
A prose swap must not change the structural verdict. A keyword matcher on
description is shown to false-positive the look-alike.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detect as D  # noqa: E402
import keyword_control as K  # noqa: E402

FIXTURES = HERE / "fixtures" / "components.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0176-probe1 {msg}")
    return 1


def by_id(components: list[dict]) -> dict[str, dict]:
    return {c["id"]: c for c in components}


def pair_result(index: dict[str, dict], a: str, b: str) -> dict:
    return D.detect_pair(index[a], index[b])


def main() -> int:
    doc = json.loads(FIXTURES.read_text(encoding="utf-8"))
    components = doc["components"]
    index = by_id(components)
    if len(index) != len(components):
        return fail("duplicate component ids")

    for comp in components:
        ok, hits = D.individually_valid_component(comp)
        print(f"individual id={comp['id']} valid={ok} hits={hits}")
        if not ok:
            return fail(f"component {comp['id']} is not individually valid")

    conflict_pairs = [tuple(p) for p in doc["expected_conflicts"]]
    compatible_pairs = [tuple(p) for p in doc["expected_compatible"]]
    if len(conflict_pairs) < 2 or len(compatible_pairs) < 1:
        return fail("fixture expected pairs too small")

    fired = []
    for a, b in conflict_pairs:
        result = pair_result(index, a, b)
        print(
            f"conflict_pair {a} vs {b} conflict={result['conflict']} "
            f"stop={result['stop']} tool={result['tool']}"
        )
        if not result["conflict"]:
            return fail(f"expected conflict silent: {a} vs {b}")
        fired.append(f"{a}|{b}")

    silent = []
    for a, b in compatible_pairs:
        result = pair_result(index, a, b)
        print(
            f"compatible_pair {a} vs {b} conflict={result['conflict']} "
            f"stop={result['stop']} tool={result['tool']}"
        )
        if result["conflict"]:
            return fail(f"look-alike false positive: {a} vs {b}")
        silent.append(f"{a}|{b}")

    # Prose swap: copy look-alike descriptions onto the conflicting trees and
    # vice versa. Structural verdicts must be unchanged.
    swapped = copy.deepcopy(index)
    la, lb = compatible_pairs[0]
    ca, cb = conflict_pairs[0]
    swapped[ca]["description"] = index[la]["description"]
    swapped[cb]["description"] = index[lb]["description"]
    swapped[la]["description"] = index[ca]["description"]
    swapped[lb]["description"] = index[cb]["description"]
    swap_conflict = D.detect_pair(swapped[ca], swapped[cb])
    swap_compat = D.detect_pair(swapped[la], swapped[lb])
    print(
        f"prose_swap conflict_still={swap_conflict['conflict']} "
        f"lookalike_still_silent={not swap_compat['conflict']}"
    )
    if not swap_conflict["conflict"]:
        return fail("prose swap hid a real conflict")
    if swap_compat["conflict"]:
        return fail("prose swap created a false positive")

    kw_conflict = K.keyword_conflict(index[ca], index[cb])
    kw_lookalike = K.keyword_conflict(index[la], index[lb])
    print(
        f"keyword_control conflict_pair={kw_conflict} lookalike={kw_lookalike} "
        f"(lookalike must be True so the control can false-positive)"
    )
    if not kw_lookalike:
        return fail("keyword control did not fire on look-alike prose")

    print(
        f"fired_on_contradiction={fired} silent_on_lookalike={silent} "
        f"prose_independent=True keyword_false_positive=True"
    )
    print("SUCCESS:IMP-0176-probe1 contradictory flagged; look-alike not flagged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
