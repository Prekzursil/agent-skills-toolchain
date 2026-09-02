#!/usr/bin/env python3
"""Named probe 1: planted orphan in each registry + both-states eight zeros."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
import join as J  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0030-probe1 {msg}")
    return 1


def main() -> int:
    good = F.consistent_fixture()
    good_join = J.join_registries(
        good["catalog"], good["artifact"], good["test"], good["claim"]
    )
    zeros = J.counts_map(good_join)
    print(f"both_states_good={json.dumps(zeros, sort_keys=True)}")
    if not good_join.get("all_eight_zero"):
        return fail("consistent fixture was not eight zeros")
    if any(int(v) != 0 for v in zeros.values()):
        return fail("consistent fixture had a non-zero directed count")
    if len(zeros) != 8:
        return fail(f"expected 8 directed counts, got {len(zeros)}")

    reports = []
    for name in ("catalog", "artifact", "test", "claim"):
        spec = F.PLANTS[name]
        docs = spec["builder"]()
        result = J.join_registries(
            docs["catalog"], docs["artifact"], docs["test"], docs["claim"]
        )
        row = result["by_direction"][spec["expected_direction"]]
        planted = spec["planted_id"]
        fired = planted in (row.get("ids") or [])
        print(
            f"plant[{name}] direction={spec['expected_direction']} "
            f"id={planted} fired={fired} count={row['count']} "
            f"nonzero={result['nonzero_directions']}"
        )
        if not fired:
            return fail(f"planted {name} orphan {planted} not in {spec['expected_direction']}")
        if result.get("all_eight_zero"):
            return fail(f"planted {name} produced eight zeros")
        reports.append(json.dumps(J.counts_map(result), sort_keys=True))

    if len(set(reports)) != 4:
        return fail("four planted reports were not distinct")
    print("four_separate_reports=True both_states_eight_zeros=True")
    print("SUCCESS:SYN-0030-probe1 planted-orphans both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
