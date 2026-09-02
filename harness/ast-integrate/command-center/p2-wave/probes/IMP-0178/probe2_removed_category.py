#!/usr/bin/env python3
"""Probe 2: removing a category from the fixture changes the computed sum.

A detector that returns a constant total is silent on this mutation.
Also: family declared-count vs leaf-count mismatch fires after a leaf drop.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from taxonomy import parse_spec, load_spec  # noqa: E402

SPEC = HERE / "fixtures" / "spec_taxonomy.md"
REMOVED = "watchlist"


def main() -> int:
    good = load_spec(SPEC)
    if good.inconsistencies:
        print("FAILED:IMP-0178-probe2 good fixture inconsistent", good.inconsistencies)
        return 1
    if REMOVED not in good.ids:
        print(f"FAILED:IMP-0178-probe2 control leaf {REMOVED} missing from fixture")
        return 1

    text = SPEC.read_text(encoding="utf-8")
    needle = f"- {REMOVED}\n"
    if needle not in text:
        print(f"FAILED:IMP-0178-probe2 cannot locate leaf line for {REMOVED}")
        return 1
    mutated = text.replace(needle, "", 1)
    if mutated == text:
        print("FAILED:IMP-0178-probe2 mutation did not change text")
        return 1

    bad = parse_spec(mutated, source_path="<mutated>")
    good_sum = good.leaf_total
    bad_sum = bad.leaf_total
    fired = bad_sum != good_sum
    mismatch = any(s.startswith("count-mismatch:") for s in bad.inconsistencies)

    if not fired:
        print(
            f"FAILED:IMP-0178-probe2 detector silent: good_sum={good_sum} "
            f"bad_sum={bad_sum} (hardcoded total?)"
        )
        return 1
    if bad_sum != good_sum - 1:
        print(
            f"FAILED:IMP-0178-probe2 expected drop of 1, got good={good_sum} bad={bad_sum}"
        )
        return 1
    if REMOVED in bad.ids:
        print(f"FAILED:IMP-0178-probe2 removed leaf {REMOVED} still present")
        return 1
    if not mismatch:
        print(
            "FAILED:IMP-0178-probe2 family checksum did not fire after leaf removal",
            bad.inconsistencies,
        )
        return 1

    # Restored text must recount to the original sum (silent on good).
    restored = parse_spec(text, source_path=str(SPEC))
    if restored.leaf_total != good_sum or restored.inconsistencies:
        print("FAILED:IMP-0178-probe2 restored fixture not silent-on-good")
        return 1

    print(
        f"good_sum={good_sum} bad_sum={bad_sum} removed={REMOVED} "
        f"fired_on_bad={fired} checksum_mismatch={mismatch} silent_on_good=True"
    )
    print("SUCCESS:IMP-0178-probe2 removed category changes computed sum")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
